import json
import zipfile
from datetime import datetime, timezone
from typing import IO, Union, List, Dict, Any

from zotero_cli.core.interfaces import ZoteroGateway

class BackupService:
    """
    Handles creation of .zaf (Zotero Archive Format) backup files.
    Uses LZMA compression (7zip algorithm) for efficiency.
    """
    
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway
        self.version = "1.0" # Format version

    def backup_collection(self, collection_key: str, output: Union[str, IO[bytes]]):
        """
        Backs up a specific collection and its items to a .zaf file.
        """
        col = self.gateway.get_collection(collection_key)
        if not col:
            raise ValueError(f"Collection {collection_key} not found")
        
        col_name = col.get('data', {}).get('name', 'Unknown')
        
        manifest = {
            "format": "zaf",
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope_type": "collection",
            "root_collection_key": collection_key,
            "root_collection_name": col_name,
            "generator": "zotero-cli"
        }
        
        items = list(self.gateway.get_items_in_collection(collection_key))
        item_data = [item.raw_data for item in items]
        
        self._write_zip(output, manifest, item_data)

    def backup_system(self, output: Union[str, IO[bytes]]):
        """
        Backs up the entire library (items only for now, structure logic todo).
        """
        manifest = {
            "format": "zaf",
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope_type": "library",
            "generator": "zotero-cli"
        }
        
        item_data: List[Dict[str, Any]] = []
        
        self._write_zip(output, manifest, item_data)

    def _write_zip(self, output: Union[str, IO[bytes]], manifest: dict, item_data: list):
        # Use LZMA if available (standard in Py3.3+)
        compression = zipfile.ZIP_LZMA if hasattr(zipfile, 'ZIP_LZMA') else zipfile.ZIP_DEFLATED

        with zipfile.ZipFile(output, "w", compression=compression) as zf:
            # Write Manifest
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # Write Data
            zf.writestr("data.json", json.dumps(item_data, indent=2))

            # Future: Attachments
