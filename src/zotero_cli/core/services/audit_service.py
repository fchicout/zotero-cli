from dataclasses import dataclass, field
from typing import List, Optional
import concurrent.futures
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

@dataclass
class AuditReport:
    total_items: int = 0
    items_missing_id: List[ZoteroItem] = field(default_factory=list)
    items_missing_title: List[ZoteroItem] = field(default_factory=list)
    items_missing_abstract: List[ZoteroItem] = field(default_factory=list)
    items_missing_pdf: List[ZoteroItem] = field(default_factory=list)

class CollectionAuditor:
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def audit_collection(self, collection_name: str) -> Optional[AuditReport]:
        collection_id = self.gateway.get_collection_id_by_name(collection_name)
        if not collection_id:
            print(f"Collection '{collection_name}' not found.")
            return None

        report = AuditReport()
        items_to_check_pdf = []
        
        # 1. Fetch items and perform local checks
        for item in self.gateway.get_items_in_collection(collection_id):
            report.total_items += 1

            if not item.has_identifier():
                report.items_missing_id.append(item)
            if not item.title:
                report.items_missing_title.append(item)
            if not item.abstract:
                report.items_missing_abstract.append(item)
            
            items_to_check_pdf.append(item)

        # 2. Check for PDF attachments in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Create a map of future -> item
            future_to_item = {
                executor.submit(self._has_pdf_attachment, item.key): item 
                for item in items_to_check_pdf
            }
            
            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    has_pdf = future.result()
                    if not has_pdf:
                        report.items_missing_pdf.append(item)
                except Exception as exc:
                    print(f"Error checking PDF for item {item.key}: {exc}")
                    # Assume missing if check failed? Or just log.
                    # report.items_missing_pdf.append(item) 

        return report

    def _has_pdf_attachment(self, item_key: str) -> bool:
        children = self.gateway.get_item_children(item_key)
        for child in children:
            if child.get('data', {}).get('itemType') == 'attachment' and \
               child.get('data', {}).get('linkMode') == 'imported_file' and \
               child.get('data', {}).get('filename', '').lower().endswith('.pdf'):
                return True
        return False
