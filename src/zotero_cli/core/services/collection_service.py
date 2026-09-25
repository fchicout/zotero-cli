import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from zotero_cli.core.interfaces import CollectionRepository, ItemRepository
from zotero_cli.core.zotero_item import ZoteroItem


@dataclass
class CollectionRemovalPlan:
    """Items to take out of one collection (they stay in the library)."""

    collection_key: str
    items: List[ZoteroItem]

    @property
    def becomes_unfiled(self) -> List[ZoteroItem]:
        """Items filed only in this collection: afterwards they are in no
        collection (still in the library, under "Unfiled Items")."""
        return [i for i in self.items if set(i.collections) <= {self.collection_key}]


@dataclass
class RecursiveDeletePlan:
    root_key: str
    collections: List[Tuple[str, int, str]]  # (key, version, name), deepest first
    items_to_delete: List[ZoteroItem] = field(default_factory=list)
    shared_items: List[ZoteroItem] = field(default_factory=list)


@dataclass
class RecursiveDeleteResult:
    deleted_items: int = 0
    deleted_collections: int = 0
    failed_items: List[str] = field(default_factory=list)
    failed_collections: List[str] = field(default_factory=list)


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
        root_keywords = ["/", "root", "unfiled"]
        is_dest_root = dest_col_name.lower() in root_keywords

        dest_id: Optional[str] = None
        if is_dest_root:
            dest_id = None  # Root
        else:
            dest_id = self.collection_repo.get_collection_id_by_name(dest_col_name)
            if not dest_id:
                dest_id = dest_col_name

        # Fetch item first
        item = self.item_repo.get_item(identifier)
        if not item:
            # Try slow lookup if key failed (only if source is provided, otherwise we can't search in it)
            if source_col_name:
                is_source_root = source_col_name.lower() in root_keywords
                if not is_source_root:
                    lookup_source_id = (
                        self.collection_repo.get_collection_id_by_name(source_col_name)
                        or source_col_name
                    )
                    print(
                        f"Item key '{identifier}' lookup failed. Searching by DOI/ArXiv in '{source_col_name}'..."
                    )
                    found_items = list(
                        self.collection_repo.get_items_in_collection(lookup_source_id)
                    )
                    for i in found_items:
                        if self._is_match(i, identifier):
                            item = i
                            break

            if not item:
                print(f"Item '{identifier}' not found.")
                return False

        # Resolve Source ID
        source_id: Optional[str] = None
        is_source_root = False

        if source_col_name:
            if source_col_name.lower() in root_keywords:
                is_source_root = True
                source_id = None
            else:
                source_id = self.collection_repo.get_collection_id_by_name(source_col_name)
                if not source_id:
                    source_id = source_col_name
        else:
            # Auto-inference
            current_cols = set(item.collections)
            # Remove dest_id if present to see what's left
            candidates = current_cols - ({dest_id} if dest_id else set())

            if len(candidates) == 0:
                if not current_cols:
                    # Item is in root
                    is_source_root = True
                    source_id = None
                else:
                    # Item is already only in dest
                    return True
            elif len(candidates) == 1:
                source_id = next(iter(candidates))
            else:
                print(
                    f"Error: Ambiguous source. Item '{identifier}' is in multiple collections ({candidates}). Please specify --source to ensure correct movement.",
                    file=sys.stderr,
                )
                return False

        # Verify membership
        if is_source_root:
            if not item.collections:
                return self._perform_move(item, None, dest_id)
            else:
                print(f"Item '{identifier}' found but it is NOT in the root folder.")
                return False
        elif source_id in item.collections:
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

    def _perform_move(
        self, item: ZoteroItem, source_id: Optional[str], dest_id: Optional[str]
    ) -> bool:
        """
        Performs a 'sticky' move by ensuring the item and all its children (notes, attachments)
        share the EXACT same collection membership as the parent after the move.
        """
        # 1. Calculate the NEW collection set for the parent
        parent_cols = set(item.collections)
        if source_id and source_id in parent_cols:
            parent_cols.remove(source_id)
        if dest_id:
            parent_cols.add(dest_id)

        target_cols_list = list(parent_cols)

        # 2. Fetch children keys/versions
        children_data = self.item_repo.get_item_children(item.key)

        # 3. Build the list of all objects to update (Parent + Children)
        all_to_update = [item.raw_data]
        for child in children_data:
            all_to_update.append(child)

        update_payload = []
        for obj in all_to_update:
            data = obj.get("data", obj)
            key = obj.get("key") or data.get("key")

            # RE-FETCH to get latest version (crucial for sequential moves)
            fresh_item = self.item_repo.get_item(key)
            if not fresh_item:
                continue

            current_cols = set(fresh_item.collections)
            version = fresh_item.version

            # ENFORCE IDENTITY: Children must have EXACTLY the same collections as parent
            if current_cols != parent_cols:
                payload = {"key": key, "version": version, "collections": target_cols_list}

                # CRITICAL: If item has a parent, it MUST be preserved in the bulk POST
                # otherwise Zotero API clears the relationship (orphaning).
                if fresh_item.parent_item:
                    payload["parentItem"] = fresh_item.parent_item

                update_payload.append(payload)

        if not update_payload:
            return True

        return self.item_repo.update_items(update_payload)

    def get_or_create_collection_id(self, name: str) -> str:
        col_id = self.collection_repo.get_collection_id_by_name(name)

        # If not found by name, check if 'name' is actually a valid collection key
        if not col_id and self.collection_repo.get_collection(name):
            col_id = name

        if not col_id:
            col_id = self.collection_repo.create_collection(name)

        if not col_id:
            raise ValueError(f"Collection '{name}' not found and could not be created.")
        return col_id

    # --- Resolution -------------------------------------------------------

    def resolve_collection(self, name_or_key: str) -> Optional[str]:
        """The key of the collection `name_or_key` names, or None. Raises
        AmbiguousCollectionError when a name matches several collections
        (Issue #381)."""
        key = self.collection_repo.get_collection_id_by_name(name_or_key)
        if not key and self.collection_repo.get_collection(name_or_key):
            key = name_or_key
        return key

    # --- Removing items from a collection (never deleting them) -----------

    def plan_clean(self, collection: str) -> Optional[CollectionRemovalPlan]:
        """What `collection clean` would do: take every item out of the
        collection. The items stay in the library (Issue #364)."""
        key = self.resolve_collection(collection)
        if not key:
            return None
        items = [
            i for i in self.collection_repo.get_items_in_collection(key) if key in i.collections
        ]
        return CollectionRemovalPlan(key, items)

    def plan_prune(self, included: str, excluded: str) -> Optional[CollectionRemovalPlan]:
        """What `slr prune` would do: take out of `excluded` every item that is
        also in `included`, the same item or a duplicate import matched by
        DOI/arXiv ID. Nothing is deleted (Issue #395); merging duplicate
        imports is `item merge` / `slr dedupe`'s job."""
        included_key = self.resolve_collection(included)
        excluded_key = self.resolve_collection(excluded)
        if not included_key or not excluded_key:
            return None

        included_keys: Set[str] = set()
        included_ids: Set[str] = set()
        for item in self.collection_repo.get_items_in_collection(included_key):
            included_keys.add(item.key)
            for identifier in (item.doi, item.arxiv_id):
                if identifier:
                    included_ids.add(self._normalize_id(identifier))

        def in_included(item: ZoteroItem) -> bool:
            return item.key in included_keys or any(
                identifier and self._normalize_id(identifier) in included_ids
                for identifier in (item.doi, item.arxiv_id)
            )

        matches = [
            i
            for i in self.collection_repo.get_items_in_collection(excluded_key)
            if excluded_key in i.collections and in_included(i)
        ]
        return CollectionRemovalPlan(excluded_key, matches)

    def remove_from_collection(self, plan: CollectionRemovalPlan) -> Tuple[int, List[str]]:
        """Removes the plan's items from its collection, one item at a time
        so each result is exact. Returns (removed count, keys that failed)."""
        removed, failed = 0, []
        for item in plan.items:
            remaining = [c for c in item.collections if c != plan.collection_key]
            if self.item_repo.update_item(item.key, item.version, {"collections": remaining}):
                removed += 1
            else:
                failed.append(item.key)
        return removed, failed

    # --- Deleting a collection tree ----------------------------------------

    def plan_recursive_delete(
        self, root_key: str, root_version: Optional[int] = None
    ) -> RecursiveDeletePlan:
        """What `collection delete --recursive` would delete: the collection,
        its sub-collections, and the items filed in them. Items that are
        also filed in a collection OUTSIDE the tree are listed separately:
        they are kept unless the caller includes them explicitly (#378)."""
        all_cols = self.collection_repo.get_all_collections()
        children: Dict[str, List[Dict[str, Any]]] = {}
        by_key = {str(c["key"]): c for c in all_cols}
        for c in all_cols:
            parent = c.get("data", {}).get("parentCollection")
            if parent:
                children.setdefault(str(parent), []).append(c)

        tree: List[Tuple[str, int, str]] = []

        def walk(key: str) -> None:
            for child in children.get(key, []):
                walk(str(child["key"]))
            collection = by_key.get(key) or {}
            if key == root_key and root_version is not None:
                collection = {**collection, "version": root_version}
            if collection.get("version") is None:
                collection = self.collection_repo.get_collection(key) or collection
            version = collection.get("version") or 0
            name = collection.get("data", {}).get("name", key)
            tree.append((key, cast(int, version), name))

        walk(root_key)  # deepest first, the root last
        tree_keys = {key for key, _, _ in tree}

        items: Dict[str, ZoteroItem] = {}
        for key, _, _ in tree:
            for item in self.collection_repo.get_items_in_collection(key):
                if not item.parent_item:
                    items.setdefault(item.key, item)

        plan = RecursiveDeletePlan(root_key=root_key, collections=tree)
        for item in items.values():
            if set(item.collections) - tree_keys:
                plan.shared_items.append(item)
            else:
                plan.items_to_delete.append(item)
        return plan

    def execute_recursive_delete(
        self, plan: RecursiveDeletePlan, include_shared: bool = False
    ) -> RecursiveDeleteResult:
        """Deletes the plan's items (plus the shared ones if
        `include_shared`), then its collections deepest first. Collections
        are only deleted if every item deletion succeeded, so a failure
        never leaves items orphaned out of a half-deleted tree."""
        result = RecursiveDeleteResult()
        targets = plan.items_to_delete + (plan.shared_items if include_shared else [])
        for item in targets:
            if self.item_repo.delete_item(item.key, item.version):
                result.deleted_items += 1
            else:
                result.failed_items.append(item.key)
        if result.failed_items:
            return result
        for key, version, _ in plan.collections:
            if self.collection_repo.delete_collection(key, version):
                result.deleted_collections += 1
            else:
                result.failed_collections.append(key)
        return result

    def delete_collection(
        self, collection_id: str, version: int, recursive: bool = False
    ) -> bool:
        """Deletes one collection; its items stay in the library. With
        `recursive`, deletes the whole tree and the items filed only inside
        it (see plan_recursive_delete)."""
        if not recursive:
            return self.collection_repo.delete_collection(collection_id, version)
        result = self.execute_recursive_delete(self.plan_recursive_delete(collection_id, version))
        return not result.failed_items and not result.failed_collections
