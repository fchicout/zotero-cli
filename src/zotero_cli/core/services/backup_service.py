import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import IO, Any, Callable, Dict, List, Optional, Set, Union

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class BackupService:
    """
    Handles creation of .zaf (Zotero Archive Format) backup files.
    Uses LZMA compression (7zip algorithm) for efficiency.
    Supports recursive attachment hydration and system-wide coverage.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway
        self.version = "1.1"

    def backup_collection(
        self, 
        collection_key: str, 
        output: Union[str, IO[bytes]], 
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ):
        """
        Backs up a specific collection, its items, and their attachments to a .zaf file.
        """
        col = self.gateway.get_collection(collection_key)
        if not col:
            raise ValueError(f"Collection {collection_key} not found")

        col_name = col.get("data", {}).get("name", "Unknown")

        manifest = {
            "format": "zaf",
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope_type": "collection",
            "root_collection_key": collection_key,
            "root_collection_name": col_name,
            "generator": "zotero-cli",
            "file_map": {},
        }

        # Fetch items. Converting to list to allow length calculation for progress bars if needed.
        items = list(self.gateway.get_items_in_collection(collection_key, top_only=True))
        self._write_zip(output, manifest, items, on_item_processed)

    def backup_system(
        self, 
        output: Union[str, IO[bytes]], 
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ):
        """
        Backs up the entire library, including all collections and orphan items.
        """
        manifest = {
            "format": "zaf",
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope_type": "library",
            "generator": "zotero-cli",
            "file_map": {},
        }

        items = list(self.gateway.get_all_items())
        self._write_zip(output, manifest, items, on_item_processed)

    def _write_zip(
        self, 
        output: Union[str, IO[bytes]], 
        manifest: dict, 
        items: List[ZoteroItem],
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ):
        # Use LZMA if available (standard in Py3.3+)
        compression = zipfile.ZIP_LZMA if hasattr(zipfile, "ZIP_LZMA") else zipfile.ZIP_DEFLATED
        
        errors: List[str] = []
        item_data: List[Dict[str, Any]] = []
        processed_keys: Set[str] = set()

        with zipfile.ZipFile(output, "w", compression=compression) as zf:
            for item in items:
                if item.key in processed_keys:
                    continue
                
                item_data.append(item.raw_data)
                processed_keys.add(item.key)
                
                # Process children
                self._process_item_recursive(item, zf, manifest, errors, item_data, processed_keys)
                
                # Notify progress
                if on_item_processed:
                    on_item_processed(item)

            # Write Manifest (including updated file_map)
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # Write Data
            zf.writestr("data.json", json.dumps(item_data, indent=2))
            
            # Write collections structure for library backups
            if manifest["scope_type"] == "library":
                collections = self.gateway.get_all_collections()
                zf.writestr("collections.json", json.dumps(collections, indent=2))

            # Write Errors if any
            if errors:
                zf.writestr("errors.log", "\n".join(errors))

    def _process_item_recursive(
        self, 
        item: ZoteroItem, 
        zf: zipfile.ZipFile, 
        manifest: dict, 
        errors: List[str],
        item_data: List[Dict[str, Any]],
        processed_keys: Set[str]
    ):
        """
        Recursively processes an item and its children (attachments/notes).
        """
        if item.item_type in ["attachment", "note"]:
            return

        children = self.gateway.get_item_children(item.key)
        for child_raw in children:
            child_key = child_raw.get("key")
            if not child_key or child_key in processed_keys:
                continue
                
            child = self.gateway.get_item(child_key)
            if not child:
                errors.append(f"Could not fetch child item {child_key} for parent {item.key}")
                continue

            item_data.append(child.raw_data)
            processed_keys.add(child.key)

            # Check if it's an attachment with a file
            data = child.raw_data.get("data", {})
            if data.get("itemType") == "attachment" and data.get("linkMode") in ["imported_file", "linked_file"]:
                filename = data.get("filename") or data.get("title")
                if filename:
                    storage_path = f"attachments/{item.key}/{filename}"
                    try:
                        with tempfile.NamedTemporaryFile(delete=False) as tf:
                            temp_path = tf.name
                        
                        if self.gateway.download_attachment(child_key, temp_path):
                            zf.write(temp_path, storage_path)
                            manifest["file_map"][child_key] = storage_path
                        else:
                            errors.append(f"Failed to download attachment {child_key} ({filename})")
                        
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception as e:
                        errors.append(f"Error processing attachment {child_key}: {str(e)}")
                        if 'temp_path' in locals() and os.path.exists(temp_path):
                            os.remove(temp_path)
            
            # Recurse
            self._process_item_recursive(child, zf, manifest, errors, item_data, processed_keys)
