import sys
from typing import Optional, Set

from zotero_cli.core.interfaces import CollectionRepository, ItemRepository
from zotero_cli.core.zotero_item import ZoteroItem


class CollectionService:
    def __init__(self, item_repo: ItemRepository, collection_repo: CollectionRepository):
        self.item_repo = item_repo
        self.collection_repo = collection_repo

    def move_item(
        self, source_col_name: Optional[str], dest_col_name: str, identifier: str
    ) -> bool:
        """
        Moves a paper identified by Key, DOI or arXiv ID from source collection to destiny collection.
        If source_col_name is None, attempts to infer it from the item's current collections.
        Returns True if successful, False if item not found, ambiguous source, or error.
        """
        dest_id = self.collection_repo.get_collection_id_by_name(dest_col_name)
        if not dest_id:
            dest_id = dest_col_name

        # Fetch item first
        item = self.item_repo.get_item(identifier)
        if not item:
            # Try slow lookup if key failed (only if source is provided, otherwise we can't search in it)
            if source_col_name:
                lookup_source_id = (
                    self.collection_repo.get_collection_id_by_name(source_col_name)
                    or source_col_name
                )
                print(
                    f"Item key '{identifier}' lookup failed. Searching by DOI/ArXiv in '{source_col_name}'..."
                )
                found_items = list(self.collection_repo.get_items_in_collection(lookup_source_id))
                for i in found_items:
                    if self._is_match(i, identifier):
                        item = i
                        break

            if not item:
                print(f"Item '{identifier}' not found.")
                return False

        # Resolve Source ID
        source_id: Optional[str] = None
        if source_col_name:
            source_id = self.collection_repo.get_collection_id_by_name(source_col_name)
            if not source_id:
                source_id = source_col_name
        else:
            # Auto-inference
            current_cols = set(item.collections)
            # Remove dest_id if present to see what's left
            candidates = current_cols - {dest_id}

            if len(candidates) == 0:
                # Just add to dest
                return self.item_repo.update_item(
                    item.key, item.version, {"collections": list(current_cols | {dest_id})}
                )
            elif len(candidates) == 1:
                source_id = list(candidates)[0]
            else:
                print(
                    f"Error: Ambiguous source. Item '{identifier}' is in multiple collections ({candidates}). Please specify --source to ensure correct movement.",
                    file=sys.stderr,
                )
                return False

        # Verify membership
        if source_id in item.collections:
            return self._perform_move(item, source_id, dest_id)
        else:
            print(
                f"Item '{identifier}' found but not in source collection '{source_col_name or source_id}'."
            )
            return False

    def _is_match(self, item: ZoteroItem, identifier: str) -> bool:
        if item.doi:
            if self._normalize_id(item.doi) == self._normalize_id(identifier):
                return True
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
            return True

        new_cols = current_cols.copy()
        if source_id in new_cols:
            new_cols.remove(source_id)
        new_cols.add(dest_id)

        return self.item_repo.update_item(key, version, {"collections": list(new_cols)})

    def get_or_create_collection_id(self, name: str) -> str:
        col_id = self.collection_repo.get_collection_id_by_name(name)
        if not col_id:
            col_id = self.collection_repo.create_collection(name)
        if not col_id:
            raise ValueError(f"Collection '{name}' not found and could not be created.")
        return col_id

    def empty_collection(
        self,
        collection_name: str,
        verbose: bool = False,
        parent_collection_name: Optional[str] = None,
    ) -> int:
        """
        Deletes all items within a specific collection.
        Returns the number of deleted items.
        """
        target_id: Optional[str] = None

        if parent_collection_name:
            # Resolve parent ID
            parent_id = (
                self.collection_repo.get_collection_id_by_name(parent_collection_name)
                or parent_collection_name
            )

            # Search all collections for the one with this parent
            all_cols = self.collection_repo.get_all_collections()
            for col in all_cols:
                data = col.get("data", col)
                if (
                    data.get("name") == collection_name
                    and data.get("parentCollection") == parent_id
                ):
                    target_id = col["key"]
                    break
        else:
            target_id = (
                self.collection_repo.get_collection_id_by_name(collection_name) or collection_name
            )

        if not target_id:
            return 0

        deleted_count = 0
        items = list(self.collection_repo.get_items_in_collection(target_id))

        for item in items:
            if self.item_repo.delete_item(item.key, item.version):
                deleted_count += 1
            else:
                print(f"Failed to delete item {item.key}")

        return deleted_count

    def prune_intersection(self, primary_col: str, secondary_col: str) -> int:
        """
        Removes items from 'secondary_col' if they are also present in 'primary_col'.
        Uses DOI/ArXiv ID for robust matching across duplicate imports.
        """
        primary_id = self.collection_repo.get_collection_id_by_name(primary_col) or primary_col
        secondary_id = (
            self.collection_repo.get_collection_id_by_name(secondary_col) or secondary_col
        )

        # 1. Map Identifiers in Primary
        primary_identifiers: Set[str] = set()
        primary_keys: Set[str] = set()

        for item in self.collection_repo.get_items_in_collection(primary_id):
            primary_keys.add(item.key)
            if item.doi:
                primary_identifiers.add(self._normalize_id(item.doi))
            if item.arxiv_id:
                primary_identifiers.add(self._normalize_id(item.arxiv_id))

        # 2. Iterate Secondary and Check for matches
        secondary_items = list(self.collection_repo.get_items_in_collection(secondary_id))

        pruned_count = 0
        for item in secondary_items:
            is_duplicate = False

            # Match by Key (Shared object)
            if item.key in primary_keys:
                is_duplicate = True
            # Match by DOI
            elif item.doi and self._normalize_id(item.doi) in primary_identifiers:
                is_duplicate = True
            # Match by ArXiv
            elif item.arxiv_id and self._normalize_id(item.arxiv_id) in primary_identifiers:
                is_duplicate = True

            if is_duplicate:
                # ACTION: Remove from secondary
                if item.key in primary_keys:
                    # Same object -> Remove collection reference
                    current_cols = set(item.collections)
                    if secondary_id in current_cols:
                        current_cols.remove(secondary_id)
                        if self.item_repo.update_item(
                            item.key, item.version, {"collections": list(current_cols)}
                        ):
                            pruned_count += 1
                else:
                    # Different object (Duplicate import) -> Delete secondary item entirely
                    if self.item_repo.delete_item(item.key, item.version):
                        pruned_count += 1

        return pruned_count
