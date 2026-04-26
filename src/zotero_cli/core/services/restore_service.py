import json
import logging
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)

@dataclass
class RestoreReport:
    collections_created: int = 0
    items_created: int = 0
    items_skipped_existing: int = 0
    attachments_uploaded: int = 0
    errors: List[str] = field(default_factory=list)
    is_dry_run: bool = False

class RestoreService:
    """
    Handles restoration of Zotero libraries and collections from .zaf archives.
    Implements idempotency, hierarchy reconstruction, and asset re-linking.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway
        self.item_map: Dict[str, str] = {}  # old_key -> new_key
        self.coll_map: Dict[str, str] = {}  # old_key -> new_key

    def restore_archive(self, file_path: str, dry_run: bool = False) -> RestoreReport:
        report = RestoreReport(is_dry_run=dry_run)

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                items_data = json.loads(zf.read("data.json").decode("utf-8"))
                
                collections_data = []
                if "collections.json" in zf.namelist():
                    collections_data = json.loads(zf.read("collections.json").decode("utf-8"))

                # 1. Reconstruct Collections
                if collections_data:
                    self._restore_collections(collections_data, report)
                elif manifest.get("scope_type") == "collection":
                    # For collection-scoped backups, we might need to ensure the root collection exists
                    # This is tricky if it was deleted. For now, we assume library-scoped for full restore
                    # and collection-scoped might just create a new one.
                    pass

                # 2. Restore Items (Top-level first, then children)
                # Sort items so parents are created before children
                sorted_items = self._sort_items_by_hierarchy(items_data)
                
                for item_raw in sorted_items:
                    self._restore_single_item(item_raw, zf, manifest, report)

        except Exception as e:
            report.errors.append(f"Critical error during restore: {str(e)}")

        return report

    def _restore_collections(self, colls: List[dict], report: RestoreReport):
        # Sort by depth to ensure parents are created before children
        # (Assuming 'parentCollection' field exists)
        
        def get_depth(c, all_colls):
            parent = c.get("data", {}).get("parentCollection")
            if not parent:
                return 0
            # Find parent in list
            parent_coll = next((pc for pc in all_colls if pc["key"] == parent), None)
            if not parent_coll:
                return 0 # Orphan
            return 1 + get_depth(parent_coll, all_colls)

        sorted_colls = sorted(colls, key=lambda c: get_depth(c, colls))

        for c_raw in sorted_colls:
            old_key = c_raw["key"]
            name = c_raw["data"]["name"]
            old_parent = c_raw["data"].get("parentCollection")
            new_parent = self.coll_map.get(old_parent) if old_parent else None

            # Idempotency check: Does collection with this name exist under this parent?
            existing_cols = self.gateway.get_all_collections()
            match = next((ec for ec in existing_cols if ec["data"]["name"] == name and ec["data"].get("parentCollection") == new_parent), None)
            
            if match:
                self.coll_map[old_key] = match["key"]
            else:
                if report.is_dry_run:
                    self.coll_map[old_key] = f"DRY_RUN_{old_key}"
                    report.collections_created += 1
                else:
                    new_key = self.gateway.create_collection(name, parent_key=new_parent)
                    if new_key:
                        self.coll_map[old_key] = new_key
                        report.collections_created += 1
                    else:
                        report.errors.append(f"Failed to create collection: {name}")

    def _restore_single_item(self, item_raw: dict, zf: zipfile.ZipFile, manifest: dict, report: RestoreReport):
        data = item_raw.get("data", {})
        item_type = data.get("itemType")
        old_key = item_raw["key"]

        if item_type in ["attachment", "note"]:
            self._restore_child_item(item_raw, zf, manifest, report)
            return

        # 1. Idempotency: Check by DOI, ArXiv ID, or Title [SPEC-ZAF-002]
        existing_item = self._find_existing_item(data)
        if existing_item:
            self.item_map[old_key] = existing_item.key
            report.items_skipped_existing += 1
            return

        # 2. Prepare new item data
        new_data = data.copy()
        # Remove keys that shouldn't be in a create request
        for k in ["key", "version", "dateAdded", "dateModified"]:
            new_data.pop(k, None)

        # Map Collections
        old_colls = data.get("collections", [])
        new_colls = [self.coll_map.get(ck) for ck in old_colls if self.coll_map.get(ck)]
        new_data["collections"] = new_colls

        # 3. Create Item
        if report.is_dry_run:
            self.item_map[old_key] = f"DRY_RUN_{old_key}"
            report.items_created += 1
        else:
            # We need a method to create generic items from raw data
            # Gateway has create_generic_item
            new_key = self.gateway.create_generic_item(new_data)
            if new_key:
                self.item_map[old_key] = new_key
                report.items_created += 1
            else:
                report.errors.append(f"Failed to create item: {data.get('title', 'Unknown')}")

    def _restore_child_item(self, child_raw: dict, zf: zipfile.ZipFile, manifest: dict, report: RestoreReport):
        data = child_raw.get("data", {})
        item_type = data.get("itemType")
        old_key = child_raw["key"]
        old_parent = data.get("parentItem")
        new_parent = self.item_map.get(old_parent)

        if not new_parent:
            # Parent not restored/found yet. This shouldn't happen with sorted items.
            return

        if item_type == "note":
            self._restore_note(data, new_parent, report)
        elif item_type == "attachment":
            self._restore_attachment(child_raw, zf, manifest, new_parent, report)

    def _restore_note(self, data: dict, new_parent: str, report: RestoreReport):
        note_content = data.get("note", "")
        if report.is_dry_run:
            return
        
        # Check if parent already has this note (very basic check)
        children = self.gateway.get_item_children(new_parent)
        for child in children:
            if child.get("data", {}).get("itemType") == "note":
                if child.get("data", {}).get("note") == note_content:
                    return

        self.gateway.create_note(new_parent, note_content)

    def _restore_attachment(self, child_raw: dict, zf: zipfile.ZipFile, manifest: dict, new_parent: str, report: RestoreReport):
        data = child_raw.get("data", {})
        old_key = child_raw["key"]
        link_mode = data.get("linkMode")
        
        if link_mode not in ["imported_file", "linked_file"]:
            return

        file_info = manifest.get("file_map", {}).get(old_key)
        if not file_info:
            return

        path_in_zip = file_info if isinstance(file_info, str) else file_info.get("path")
        if not path_in_zip or path_in_zip not in zf.namelist():
            return

        if report.is_dry_run:
            report.attachments_uploaded += 1
            return

        import os
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(path_in_zip)[1]) as tf:
                temp_path = tf.name
                tf.write(zf.read(path_in_zip))

            if self.gateway.upload_attachment(new_parent, temp_path):
                report.attachments_uploaded += 1
            else:
                report.errors.append(f"Failed to upload attachment: {path_in_zip}")
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            report.errors.append(f"Failed to upload attachment {path_in_zip}: {str(e)}")

    def _find_existing_item(self, data: dict) -> Optional[ZoteroItem]:
        from zotero_cli.core.models import ZoteroQuery
        
        # Search by DOI
        doi = data.get("DOI")
        if doi:
            items = list(self.gateway.get_items_by_doi(doi))
            if items: return items[0]

        # Search by Title (Exact)
        title = data.get("title")
        if title:
            # This is slow if we do it for every item. Ideally gateway has a search by title.
            # For now, we might skip full library scans if performance is an issue.
            pass

        return None

    def _sort_items_by_hierarchy(self, items: List[dict]) -> List[dict]:
        # Simple two-pass sort: top-level items, then children
        parents = []
        children = []
        for i in items:
            if i.get("data", {}).get("itemType") in ["attachment", "note"]:
                children.append(i)
            else:
                parents.append(i)
        return parents + children
