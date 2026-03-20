import os
import tempfile
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
)
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.services.pdf_finder_service import PDFFinderService
from zotero_cli.core.services.purge_service import PurgeService
from zotero_cli.core.utils.slugify import slugify
from zotero_cli.core.zotero_item import ZoteroItem


class AttachmentService:
    def __init__(
        self,
        item_repo: ItemRepository,
        collection_repo: CollectionRepository,
        attachment_repo: AttachmentRepository,
        note_repo: NoteRepository,
        metadata_aggregator: MetadataAggregatorService,
        purge_service: Optional[PurgeService] = None,
        pdf_finder: Optional[PDFFinderService] = None,
    ):
        self.item_repo = item_repo
        self.collection_repo = collection_repo
        self.attachment_repo = attachment_repo
        self.note_repo = note_repo
        self.metadata_aggregator = metadata_aggregator
        self.purge_service = purge_service
        self.pdf_finder = pdf_finder

    def _get_purge_service(self) -> PurgeService:
        if not self.purge_service:
            # This is a bit hacky but avoids refactoring all factory calls at once if needed,
            # though we will update the factory.
            from zotero_cli.infra.factory import GatewayFactory

            self.purge_service = GatewayFactory.get_purge_service()
        return self.purge_service

    def _get_pdf_finder(self) -> PDFFinderService:
        if not self.pdf_finder:
            from zotero_cli.infra.factory import GatewayFactory

            self.pdf_finder = GatewayFactory.get_pdf_finder_service()
        return self.pdf_finder

    def attach_pdfs_to_collection(self, collection_name: str) -> List[int]:
        col_id = self.collection_repo.get_collection_id_by_name(collection_name)
        if not col_id:
            print(f"Collection '{collection_name}' not found.")
            return []

        job_ids = []
        items = self.collection_repo.get_items_in_collection(col_id)
        pdf_finder = self._get_pdf_finder()

        for item in items:
            if not self._has_pdf_attachment(item.key):
                jid = pdf_finder.enqueue_find_pdf(item.key)
                job_ids.append(jid)

        return job_ids

    def attach_pdf_to_item(self, item_key: str) -> bool:
        """Attempts to find and attach a PDF to a single item."""
        # 1. Check if item exists and already has PDF
        item = self.item_repo.get_item(item_key)
        if not item:
            print(f"Item '{item_key}' not found.")
            return False

        if self._has_pdf_attachment(item_key):
            return False

        # 2. Try existing URL if it looks like a PDF
        if item.url and self._looks_like_pdf(item.url):
            print(f"Checking existing URL for PDF: {item.url}")
            pdf_path = self._download_file(item.url)
            if pdf_path:
                print("  Uploading to Zotero...")
                success = self.attachment_repo.upload_attachment(item_key, pdf_path)
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                if success:
                    print("  Success from existing URL!")
                    return True

        identifier = item.doi or item.arxiv_id
        if not identifier:
            return False

        print(f"Checking PDF for: {item.title} ({identifier})")

        # 3. Get Metadata (PDF URL) from aggregator
        enriched = self.metadata_aggregator.get_enriched_metadata(identifier)
        if not enriched:
            print("  No enriched metadata found.")
            return False

        pdf_url = enriched.pdf_url
        if not pdf_url and enriched.url and self._looks_like_pdf(enriched.url):
            pdf_url = enriched.url

        if not pdf_url:
            print("  No PDF URL found.")
            return False

        print(f"  Found PDF URL: {pdf_url}")

        # 4. Download
        pdf_path = self._download_file(pdf_url)
        if not pdf_path:
            print("  Failed to download PDF.")
            return False

        # 5. Upload
        print("  Uploading to Zotero...")
        success = self.attachment_repo.upload_attachment(item_key, pdf_path)

        # Cleanup
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        if success:
            print("  Success!")
        else:
            print("  Upload failed.")

        return success

    def _looks_like_pdf(self, url: str) -> bool:
        """Heuristic check if a URL likely points to a PDF file."""
        if not url:
            return False
        url_lower = url.lower()
        if url_lower.endswith(".pdf"):
            return True
        if "/pdf/" in url_lower:
            return True
        if "arxiv.org/pdf" in url_lower:
            return True
        return False

    def remove_attachments_from_collection(self, collection_name: str, dry_run: bool = True) -> int:
        warnings.warn(
            "AttachmentService.remove_attachments_from_collection is deprecated and will be removed in Phase B. Use PurgeService.purge_collection_assets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        col_id = self.collection_repo.get_collection_id_by_name(collection_name)
        if not col_id:
            print(f"Collection '{collection_name}' not found.")
            return 0

        item_keys = [item.key for item in self.collection_repo.get_items_in_collection(col_id)]
        if not item_keys:
            return 0

        stats = self._get_purge_service().purge_attachments(item_keys, dry_run=dry_run)
        return stats["deleted"] if not dry_run else stats["skipped"]

    def remove_attachments_from_item(self, item_key: str, dry_run: bool = True) -> int:
        warnings.warn(
            "AttachmentService.remove_attachments_from_item is deprecated and will be removed in Phase B. Use PurgeService.purge_item_assets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        stats = self._get_purge_service().purge_attachments([item_key], dry_run=dry_run)
        return stats["deleted"] if not dry_run else stats["skipped"]

    def _has_pdf_attachment(self, item_key: str) -> bool:
        children = self.note_repo.get_item_children(item_key)
        for child in children:
            if (
                child.get("data", {}).get("itemType") == "attachment"
                and child.get("data", {}).get("linkMode") == "imported_file"
                and child.get("data", {}).get("contentType", "") == "application/pdf"
            ):
                return True
        return False

    def _download_file(self, url: str) -> Optional[str]:
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            # Create temp file
            fd, path = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(fd, "wb") as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
            return path
        except Exception as e:
            print(f"Download error: {e}")
            return None

    def get_fulltext(self, item_key: str) -> Optional[str]:
        """
        Retrieves the full text of an item's PDF attachment as Markdown.
        """
        # 1. Find PDF attachment
        attachment_key = self._get_pdf_attachment_key(item_key)
        if not attachment_key:
            return None

        # 2. Download attachment to temp file
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        try:
            success = self.attachment_repo.download_attachment(attachment_key, temp_path)
            if not success:
                return None

            # 3. Extract text using markitdown
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(temp_path)
            return result.text_content
        except Exception as e:
            print(f"Full-text extraction error for {item_key}: {e}")
            return None
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _get_pdf_attachment_key(self, item_key: str) -> Optional[str]:
        children = self.note_repo.get_item_children(item_key)
        for child in children:
            data = child.get("data", {})
            if (
                data.get("itemType") == "attachment"
                and data.get("contentType") == "application/pdf"
            ):
                return child.get("key")
        return None

    def bulk_export_markdown(
        self, items: List[ZoteroItem], output_dir: Path, max_workers: int = 5
    ) -> Dict[str, Any]:
        """
        Bulk converts PDF attachments of given items to Markdown.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        stats = {"total": len(items), "success": 0, "failed": 0, "skipped": 0}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(self._export_item_markdown, item, output_dir): item
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
                    print(f"Error exporting {item.key}: {e}")
                    stats["failed"] += 1

        return stats

    def _export_item_markdown(self, item: ZoteroItem, output_dir: Path) -> str:
        """Helper for bulk export."""
        # 1. Check for PDF
        if not self._get_pdf_attachment_key(item.key):
            return "skipped"

        # 2. Extract text
        text = self.get_fulltext(item.key)
        if not text:
            return "failed"

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
            print(f"File write error for {item.key}: {e}")
            return "failed"
