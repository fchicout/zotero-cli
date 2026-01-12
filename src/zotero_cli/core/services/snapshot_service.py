from typing import Callable, Optional, List, Dict, Any
import json
import time
from datetime import datetime, timezone
import sys

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

# Type alias for the progress callback
# Args: current_item_index, total_items, status_message
ProgressCallback = Callable[[int, int, str], None]

class SnapshotService:
    """
    Service responsible for creating immutable snapshots of Zotero collections.
    Adheres to SOLID principles: Single Responsibility (Snapshotting).
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def freeze_collection(
        self, 
        collection_name: str, 
        output_path: str, 
        callback: Optional[ProgressCallback] = None
    ) -> bool:
        """
        Creates a JSON snapshot of the specified collection, including all child items (notes/attachments).
        
        Args:
            collection_name: The name of the collection to freeze.
            output_path: The file path to save the JSON snapshot.
            callback: Optional function to report progress (useful for CLI spinners or WebUI bars).
        
        Returns:
            bool: True if successful, False otherwise.
        """
        # 1. Resolve Collection ID
        if callback:
            callback(0, 0, "Resolving collection ID...")
        
        collection_id = self.gateway.get_collection_id_by_name(collection_name)
        if not collection_id:
            print(f"Error: Collection '{collection_name}' not found.", file=sys.stderr)
            return False

        # 2. Fetch Top-Level Items
        if callback:
            callback(0, 0, f"Fetching items from '{collection_name}'...")
        
        # We fetch raw items first to get the count
        # Optimization: In a real async world, we'd stream this. 
        # Here we materialize the list to give a proper progress bar.
        items_iter = self.gateway.get_items_in_collection(collection_id)
        parent_items = list(items_iter)
        total_items = len(parent_items)

        snapshot_data: List[Dict[str, Any]] = []

        # 3. Iterate and Enrich (The "Deep Fetch")
        for index, item in enumerate(parent_items):
            if callback:
                callback(index + 1, total_items, f"Processing: {item.title[:30] if item.title else 'Untitled'}...")

            # Convert to dict representation (we want to preserve data)
            # Since ZoteroItem is a simplified view, for a TRUE snapshot we might want raw data.
            # However, looking at the current codebase, ZoteroItem is the standard currency.
            # We will construct a snapshot object that includes the ZoteroItem fields + children.
            
            item_data = self._serialize_item(item)
            
            # Fetch Children (Notes/Attachments)
            # This is the N+1 API call bottleneck. 
            # In V2, we should use 'ZoteroAPIClient.get_items(collection=..., include=children)' if possible
            # or fetch all items in collection including children and stitch in memory.
            # For now, we follow the robust iterative approach.
            children_raw = self.gateway.get_item_children(item.key)
            
            # Nest children
            item_data['children'] = children_raw
            
            snapshot_data.append(item_data)

        # 4. Construct Final Artifact
        artifact = {
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "collection_name": collection_name,
                "collection_id": collection_id,
                "item_count": total_items,
                "tool_version": "zotero-cli-v0.4.0-dev", # Should grab from package
                "schema_version": "1.0"
            },
            "items": snapshot_data
        }

        # 5. Write to Disk
        if callback:
            callback(total_items, total_items, "Writing snapshot to disk...")
            
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(artifact, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error writing snapshot file: {e}", file=sys.stderr)
            return False

    def _serialize_item(self, item: ZoteroItem) -> Dict[str, Any]:
        """Helper to convert ZoteroItem dataclass to a clean dictionary."""
        # Using implicit __dict__ or manual mapping to ensure control
        return {
            "key": item.key,
            "version": item.version,
            "item_type": item.item_type,
            "title": item.title,
            "abstract": item.abstract,
            "doi": item.doi,
            "arxiv_id": item.arxiv_id,
            "url": item.url,
            "date": item.date,
            "authors": item.authors,
            "collections": item.collections,
            "tags": item.tags
        }
