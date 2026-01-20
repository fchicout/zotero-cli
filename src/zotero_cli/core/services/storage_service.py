import os
from pathlib import Path
from typing import List, Optional, cast

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ZoteroQuery
from zotero_cli.core.zotero_item import ZoteroItem


class StorageService:
    def __init__(
        self,
        config: ZoteroConfig,
        gateway: ZoteroGateway,
    ):
        self.config = config
        self.gateway = gateway

    def checkout_items(self, limit: int = 50) -> int:
        """
        Moves 'imported_file' attachments to local storage and converts them to 'linked_file'.
        """
        if not self.config.storage_path:
            print("Error: 'storage_path' is not configured in config.toml.")
            return 0

        storage_root = Path(self.config.storage_path)
        if not storage_root.exists():
            try:
                storage_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating storage directory: {e}")
                return 0

        print(f"Scanning for stored attachments (Limit: {limit})...")
        
        # Search for attachments
        # itemType: attachment
        query = ZoteroQuery(
            item_type="attachment",
            sort="date", # No direct size sort in API, using date as proxy for now
            direction="desc"
        )
        
        # Gateway must support search_items (it does in ZoteroAPIClient)
        # We need to cast because the interface in interfaces.py splits them up 
        # but ZoteroGateway inherits them. 
        # Wait, ZoteroGateway inherits ItemRepository but ItemRepository doesn't have search_items.
        # I need to check interfaces.py again. ArxivGateway has search, but ZoteroGateway?
        # ZoteroAPIClient implements search_items, but is it on the interface?
        
        # Let's assume we can call search_items if it exists on the implementation
        # or we update the interface.
        # Checking interfaces.py... 
        # ItemRepository has `get_items_by_tag`.
        # ZoteroGateway inherits ItemRepo...
        # It seems `search_items` is missing from ZoteroGateway interface! 
        # I should add it to ZoteroGateway interface to be safe.
        
        candidates = []
        count = 0
        
        # For now, I'll assume we can use the client directly or update interface.
        # I will update the interface in the next step to be correct.
        
        # Temporary logic assuming interface update:
        items_iter = self.gateway.search_items(query)
        
        processed = 0
        for item in items_iter:
            if processed >= limit:
                break
            
            if self.checkout_single_item(item, storage_root):
                processed += 1
                
        return processed

    def checkout_single_item(self, item: ZoteroItem, storage_root: Path) -> bool:
        # Check if it's eligible
        if item.item_type != "attachment":
            return False
        
        # Check linkMode in raw data
        link_mode = item.raw_data.get("data", {}).get("linkMode")
        if link_mode != "imported_file":
            return False

        filename = item.raw_data.get("data", {}).get("filename")
        if not filename:
            title = item.title or "untitled"
            # Basic sanitization
            safe_title = "".join([c for c in title if c.isalnum() or c in "._- "]).strip()
            filename = f"{item.key}_{safe_title}.pdf"

        # Ensure filename is safe
        filename = os.path.basename(filename)
        target_path = storage_root / filename
        
        # Handle duplicates: If file exists, try appending key
        if target_path.exists():
             filename = f"{item.key}_{filename}"
             target_path = storage_root / filename

        if target_path.exists():
            print(f"Skipping {item.key}: File {filename} already exists.")
            return False

        print(f"Processing {item.key}: {filename}...")

        # 1. Download
        try:
            if not self.gateway.download_attachment(item.key, str(target_path)):
                print(f"  Failed to download.")
                return False
        except Exception as e:
            print(f"  Exception downloading: {e}")
            if target_path.exists():
                target_path.unlink()
            return False

        # 2. Update Zotero
        try:
            if not self.gateway.update_attachment_link(item.key, item.version, str(target_path)):
                print(f"  Failed to update Zotero item. Rolling back...")
                target_path.unlink()
                return False
        except Exception as e:
            print(f"  Exception updating: {e}")
            if target_path.exists():
                target_path.unlink()
            return False

        print(f"  [green]Moved[/] to {target_path}")
        return True