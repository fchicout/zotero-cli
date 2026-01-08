from typing import Optional, List, Set
import re
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

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

    def empty_collection(self, collection_name: str, parent_collection_name: Optional[str] = None, verbose: bool = False) -> int:
        """
        Deletes all items within a specific collection.
        Returns the number of deleted items.
        """
        target_id = None
        
        if parent_collection_name:
            # Find collection inside parent
            all_cols = self.gateway.get_all_collections()
            parent_id = None
            
            # Find parent ID
            for col in all_cols:
                if col['data']['name'] == parent_collection_name:
                    parent_id = col['key']
                    break
            
            if not parent_id:
                print(f"Parent collection '{parent_collection_name}' not found.")
                return 0
                
            # Find target collection with correct parent
            for col in all_cols:
                if col['data']['name'] == collection_name and col['data'].get('parentCollection') == parent_id:
                    target_id = col['key']
                    break
            
            if not target_id:
                print(f"Collection '{collection_name}' inside '{parent_collection_name}' not found.")
                return 0
                
        else:
            # Simple lookup
            target_id = self.gateway.get_collection_id_by_name(collection_name)
            if not target_id:
                print(f"Collection '{collection_name}' not found.")
                return 0
            
        deleted_count = 0
        items = list(self.gateway.get_items_in_collection(target_id))
        
        if not items:
            if verbose:
                print(f"Collection '{collection_name}' is already empty.")
            return 0

        print(f"Found {len(items)} items in '{collection_name}'. Deleting...")
        
        for item in items:
            if self.gateway.delete_item(item.key, item.version):
                deleted_count += 1
                if verbose:
                    print(f"Deleted item {item.key}")
            else:
                print(f"Failed to delete item {item.key}")
                
        return deleted_count
