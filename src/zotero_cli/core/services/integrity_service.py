import concurrent.futures
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from zotero_cli.core.interfaces import CollectionRepository, NoteRepository
from zotero_cli.core.utils.notify import NotifyMixin
from zotero_cli.core.zotero_item import ZoteroItem


@dataclass
class AuditReport:
    total_items: int = 0
    items_missing_id: List[ZoteroItem] = field(default_factory=list)
    items_missing_title: List[ZoteroItem] = field(default_factory=list)
    items_missing_abstract: List[ZoteroItem] = field(default_factory=list)
    items_missing_pdf: List[ZoteroItem] = field(default_factory=list)


class IntegrityService(NotifyMixin):
    """
    Handles metadata completeness and asset integrity audits for collections.
    """

    def __init__(self, collections: CollectionRepository, notes: NoteRepository):
        self.collections = collections
        self.notes = notes

    def audit_collection(self, collection_name: str) -> Optional[AuditReport]:
        collection_id = self.collections.get_collection_id_by_name(collection_name)
        if not collection_id:
            # Maybe it's already a key
            collection_id = (
                collection_name if self.collections.get_collection(collection_name) else None
            )

        if not collection_id:
            return None

        report = AuditReport()
        items_to_check_children = []

        # 1. Fetch items and perform local checks (Top-level only)
        for item in self.collections.get_items_in_collection(collection_id, top_only=True):
            report.total_items += 1

            if not item.has_identifier():
                report.items_missing_id.append(item)
            if not item.title:
                report.items_missing_title.append(item)
            if not item.abstract:
                report.items_missing_abstract.append(item)

            items_to_check_children.append(item)

        # 2. Check for PDF attachments in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_item = {
                executor.submit(self._audit_children, item.key): item
                for item in items_to_check_children
            }

            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    if not future.result():
                        report.items_missing_pdf.append(item)
                except Exception as exc:
                    self._say(f"Error checking children for item {item.key}: {exc}", logging.ERROR)

        return report

    def _audit_children(self, item_key: str) -> bool:
        """Whether the item has a PDF attachment."""
        for child in self.notes.get_item_children(item_key):
            data = child.get("data", {})
            # A PDF is an attachment with a .pdf filename or a PDF content type,
            # whether imported or linked.
            is_pdf_ext = data.get("filename", "").lower().endswith(".pdf")
            is_pdf_mime = data.get("contentType") == "application/pdf"
            if data.get("itemType") == "attachment" and (is_pdf_ext or is_pdf_mime):
                return True
        return False
