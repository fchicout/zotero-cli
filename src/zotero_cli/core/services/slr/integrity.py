import concurrent.futures
from dataclasses import dataclass, field
from typing import List, Optional

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem


@dataclass
class AuditReport:
    total_items: int = 0
    items_missing_id: List[ZoteroItem] = field(default_factory=list)
    items_missing_title: List[ZoteroItem] = field(default_factory=list)
    items_missing_abstract: List[ZoteroItem] = field(default_factory=list)
    items_missing_pdf: List[ZoteroItem] = field(default_factory=list)
    items_missing_note: List[ZoteroItem] = field(default_factory=list)

class IntegrityService:
    """
    Handles metadata completeness and asset integrity audits for collections.
    """
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def audit_collection(self, collection_name: str) -> Optional[AuditReport]:
        collection_id = self.gateway.get_collection_id_by_name(collection_name)
        if not collection_id:
            # Maybe it's already a key
            collection_id = (
                collection_name if self.gateway.get_collection(collection_name) else None
            )

        if not collection_id:
            return None

        report = AuditReport()
        items_to_check_children = []

        # 1. Fetch items and perform local checks (Top-level only)
        for item in self.gateway.get_items_in_collection(collection_id, top_only=True):
            report.total_items += 1

            if not item.has_identifier():
                report.items_missing_id.append(item)
            if not item.title:
                report.items_missing_title.append(item)
            if not item.abstract:
                report.items_missing_abstract.append(item)

            items_to_check_children.append(item)

        # 2. Check for children (PDFs and Notes) in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_item = {
                executor.submit(self._audit_children, item.key): item
                for item in items_to_check_children
            }

            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    has_pdf, has_note = future.result()
                    if not has_pdf:
                        report.items_missing_pdf.append(item)
                    if not has_note:
                        report.items_missing_note.append(item)
                except Exception as exc:
                    print(f"Error checking children for item {item.key}: {exc}")

        return report

    def _audit_children(self, item_key: str) -> tuple[bool, bool]:
        """Returns (has_pdf, has_screening_note)"""
        children = self.gateway.get_item_children(item_key)
        has_pdf = False
        has_note = False

        from zotero_cli.core.utils.sdb_parser import parse_sdb_note

        for child in children:
            data = child.get("data", {})
            item_type = data.get("itemType")

            # Check PDF: look for imported_file OR linked_url with PDF contentType
            is_pdf_ext = data.get("filename", "").lower().endswith(".pdf")
            is_pdf_mime = data.get("contentType") == "application/pdf"

            if item_type == "attachment" and (is_pdf_ext or is_pdf_mime):
                has_pdf = True

            # Check Screening Note: use robust parser instead of string match
            if item_type == "note":
                note_text = data.get("note", "")
                if parse_sdb_note(note_text):
                    has_note = True

        return has_pdf, has_note
