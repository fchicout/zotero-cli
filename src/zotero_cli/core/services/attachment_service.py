import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from zotero_cli.core import annotations as annotation_records
from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    FullTextProvider,
    ItemRepository,
    NoteRepository,
)
from zotero_cli.core.services.children_index import children_by_parent
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.utils.notify import NotifyMixin
from zotero_cli.core.utils.slugify import slugify
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)

# "Not looked up yet", as distinct from None ("no PDF").
_UNKNOWN: Any = object()


def extract_pdf_text(path: str) -> str:
    """
    The text of a PDF file. pdfminer.six directly (Issue #403): it's what
    markitdown used for PDFs, but markitdown was installed without its PDF
    extra and pulled in onnxruntime/magika/numpy, which the binaries exclude.
    """
    from pdfminer.high_level import extract_text

    return str(extract_text(path))


class AttachmentService(FullTextProvider, NotifyMixin):
    def __init__(
        self,
        item_repo: ItemRepository,
        collection_repo: CollectionRepository,
        attachment_repo: AttachmentRepository,
        note_repo: NoteRepository,
        metadata_aggregator: MetadataAggregatorService,
    ):
        self.item_repo = item_repo
        self.collection_repo = collection_repo
        self.attachment_repo = attachment_repo
        self.note_repo = note_repo
        self.metadata_aggregator = metadata_aggregator

    def get_fulltext(self, item_key: str, attachment_key: Optional[str] = None) -> Optional[str]:
        """
        Retrieves the text of an item's PDF attachment (plain text, saved as
        .md by the exports). Ensures zero-persistence of temporary files
        [SPEC-RAG-005]. A caller that already knows the attachment passes
        its key, saving a children lookup (Issue #432).
        """
        # 1. Find PDF attachment
        if attachment_key is None:
            attachment_key = self._get_pdf_attachment_key(item_key)
        if not attachment_key:
            return None

        # 2. Use TemporaryDirectory for strict lifecycle control
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = os.path.join(tmp_dir, f"{attachment_key}.pdf")

            try:
                success = self.attachment_repo.download_attachment(attachment_key, temp_path)
                if not success:
                    return None

                # 3. Extract the text
                return extract_pdf_text(temp_path)
            except Exception as e:
                self._say(f"Full-text extraction error for {item_key}: {e}", logging.ERROR)
                logger.exception("Full-text extraction error for %s", item_key)
                return None
            # No finally block needed here as TemporaryDirectory cleans up on __exit__

    def _get_pdf_attachment_key(self, item_key: str) -> Optional[str]:
        return self._pdf_key(self.note_repo.get_item_children(item_key))

    def pdf_attachment_keys(self, items: List[ZoteroItem]) -> Dict[str, Optional[str]]:
        """Each item's PDF attachment key (None if it has none), found for
        all items together. Markdown export made two children requests per
        item, one to check and one again to download (Issue #432)."""
        attachments = children_by_parent(self.note_repo, [i.key for i in items], "attachment")
        return {key: self._pdf_key(children) for key, children in attachments.items()}

    @staticmethod
    def _pdf_key(children: List[Dict[str, Any]]) -> Optional[str]:
        for child in children:
            data = child.get("data", {})
            if (
                data.get("itemType") == "attachment"
                and data.get("contentType") == "application/pdf"
            ):
                return child.get("key")
        return None

    def bulk_export_markdown(
        self,
        items: List[ZoteroItem],
        output_dir: Path,
        max_workers: int = 5,
        include_annotations: bool = False,
    ) -> Dict[str, Any]:
        """
        Bulk converts PDF attachments of given items to Markdown; with
        `include_annotations`, each file ends with the item's PDF annotations.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        stats = {"total": len(items), "success": 0, "failed": 0, "skipped": 0}
        pdf_keys = self.pdf_attachment_keys(items)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(
                    self._export_item_markdown,
                    item,
                    output_dir,
                    pdf_keys.get(item.key),
                    include_annotations,
                ): item
                for item in items
            }

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    if result == "success":
                        stats["success"] += 1
                    elif result == "skipped":
                        stats["skipped"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    self._say(f"Error exporting {item.key}: {e}", logging.ERROR)
                    logger.exception("Error exporting %s", item.key)
                    stats["failed"] += 1

        return stats

    def _with_annotations(self, item: ZoteroItem, text: str) -> str:
        """`text` followed by the item's annotations; unchanged if there are none or they
        can't be read (the export itself still succeeds)."""
        try:
            section = annotation_records.to_markdown(self.attachment_repo.get_annotations(item.key))
        except Exception as e:
            self._say(
                f"Warning: could not read the annotations of {item.key}: {e}", logging.WARNING
            )
            return text
        return f"{text.rstrip()}\n\n{section}" if section else text

    def _export_item_markdown(
        self,
        item: ZoteroItem,
        output_dir: Path,
        pdf_key: Optional[str] = _UNKNOWN,
        include_annotations: bool = False,
    ) -> str:
        """Helper for bulk export."""
        # 1. Check for PDF
        if pdf_key is _UNKNOWN:
            pdf_key = self._get_pdf_attachment_key(item.key)
        if not pdf_key:
            return "skipped"

        # 2. Extract text
        text = self.get_fulltext(item.key, pdf_key)
        if not text:
            return "failed"

        if include_annotations:
            text = self._with_annotations(item, text)

        # 3. Save to file
        title_slug = slugify(item.title or "Untitled")
        if len(title_slug) > 50:
            title_slug = title_slug[:50]
        filename = f"{item.key}_{title_slug}.md"
        file_path = output_dir / filename

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
            return "success"
        except Exception as e:
            self._say(f"File write error for {item.key}: {e}", logging.ERROR)
            logger.exception("File write error for %s", item.key)
            return "failed"
