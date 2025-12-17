from dataclasses import dataclass, field
from typing import List, Optional
from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.zotero_item import ZoteroItem

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
        
        for item in self.gateway.get_items_in_collection(collection_id):
            report.total_items += 1

            if not item.has_identifier():
                report.items_missing_id.append(item)
            if not item.title:
                report.items_missing_title.append(item)
            if not item.abstract:
                report.items_missing_abstract.append(item)
            
            # Check for PDF attachments
            has_pdf_attachment = False
            children = self.gateway.get_item_children(item.key)
            for child in children:
                if child.get('data', {}).get('itemType') == 'attachment' and \
                   child.get('data', {}).get('linkMode') == 'imported_file' and \
                   child.get('data', {}).get('filename', '').lower().endswith('.pdf'):
                    has_pdf_attachment = True
                    break
            
            if not has_pdf_attachment:
                report.items_missing_pdf.append(item)

        return report
