from typing import Optional, List, Set
import re
from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.zotero_item import ZoteroItem

class CollectionService:
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def move_item(self, source_col_name: str, dest_col_name: str, identifier: str) -> bool:
        """
        Moves a paper identified by DOI or arXiv ID from source collection to destiny collection.
        Returns True if successful, False if item not found or error.
        """
        source_id = self.gateway.get_collection_id_by_name(source_col_name)
        if not source_id:
            print(f"Source collection '{source_col_name}' not found.")
            return False

        dest_id = self.gateway.get_collection_id_by_name(dest_col_name)
        if not dest_id:
            print(f"Destiny collection '{dest_col_name}' not found.")
            return False

        # Iterate through items in source collection
        for item in self.gateway.get_items_in_collection(source_id):
            if self._is_match(item, identifier):
                return self._perform_move(item, source_id, dest_id)
        
        print(f"Item with identifier '{identifier}' not found in '{source_col_name}'.")
        return False

    def _is_match(self, item: ZoteroItem, identifier: str) -> bool:
        
        # Check DOI
        if item.doi:
            if self._normalize_id(item.doi) == self._normalize_id(identifier):
                return True
        
        # Check arXiv ID
        if item.arxiv_id:
            if self._normalize_id(item.arxiv_id) == self._normalize_id(identifier):
                return True

        return False

    def _normalize_id(self, identifier: str) -> str:
        return identifier.strip().lower()

    def _perform_move(self, item: ZoteroItem, source_id: str, dest_id: str) -> bool:
        key = item.key
        version = item.version
        current_cols = set(item.collections)
        
        if dest_id in current_cols and source_id not in current_cols:
            print(f"Item is already in '{dest_id}' and not in '{source_id}'.")
            return True

        new_cols = current_cols.copy()
        if source_id in new_cols:
            new_cols.remove(source_id)
        new_cols.add(dest_id)
        
        return self.gateway.update_item_collections(key, version, list(new_cols))
