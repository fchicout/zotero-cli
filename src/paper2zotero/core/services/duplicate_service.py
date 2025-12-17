from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from collections import defaultdict
import re
import unicodedata

from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.zotero_item import ZoteroItem

@dataclass
class DuplicateGroup:
    # A string representing the identifier that caused the duplication (e.g., "DOI: 10.xxxx" or "Title: My Paper")
    identifier_key: str 
    items: List[ZoteroItem] = field(default_factory=list)

class DuplicateFinder:
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def find_duplicates(self, collection_names: List[str]) -> List[DuplicateGroup]:
        all_items_by_identifier = defaultdict(list)
        
        for col_name in collection_names:
            col_id = self.gateway.get_collection_id_by_name(col_name)
            if not col_id:
                print(f"Warning: Collection '{col_name}' not found. Skipping.")
                continue
            
            for item in self.gateway.get_items_in_collection(col_id):
                normalized_doi = self._normalize_doi(item.doi) if item.doi else None
                normalized_title = self._normalize_title(item.title) if item.title else None
                
                if normalized_doi:
                    all_items_by_identifier[("doi", normalized_doi)].append(item)
                elif normalized_title:
                    all_items_by_identifier[("title", normalized_title)].append(item)
                # Items without DOI or title are not considered for this type of duplication check

        duplicate_groups = []
        for (id_type, identifier_value), items in all_items_by_identifier.items():
            if len(items) > 1:
                duplicate_groups.append(DuplicateGroup(
                    identifier_key=f"{id_type.upper()}: {identifier_value}", 
                    items=items
                ))
        return duplicate_groups

    def _normalize_doi(self, doi: str) -> str:
        return doi.strip().lower()

    def _normalize_title(self, title: str) -> str:
        # Lowercase
        title = title.lower()
        
        # Decompose unicode characters and remove non-spacing marks (accents)
        normalized_title = unicodedata.normalize('NFD', title)
        title = ''.join(c for c in normalized_title if unicodedata.category(c) != 'Mn')

        # Remove punctuation
        title = re.sub(r'[^\w\s]', '', title) 
        
        # Replace multiple spaces with single space and strip
        title = re.sub(r'\s+', ' ', title).strip() 
        
        return title