import json
import csv
import sys
from typing import List, Dict, Optional, Callable
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

# Progress Callback Type: current, total, message
ProgressCallback = Callable[[int, int, str], None]

class SyncService:
    """
    Service responsible for synchronizing local state (CSV) from remote truth (Zotero Notes).
    """
    
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def recover_state_from_notes(
        self, 
        collection_name: str, 
        output_csv_path: str,
        callback: Optional[ProgressCallback] = None
    ) -> bool:
        """
        Scans a collection, finds screening notes, and rebuilds the CSV file.
        
        Args:
            collection_name: The Zotero collection to scan.
            output_csv_path: Path to write the recovered CSV.
            callback: Optional progress reporter.
            
        Returns:
            bool: True if successful.
        """
        # 1. Resolve ID
        if callback: callback(0, 0, "Resolving collection ID...")
        collection_id = self.gateway.get_collection_id_by_name(collection_name)
        if not collection_id:
            print(f"Error: Collection '{collection_name}' not found.", file=sys.stderr)
            return False

        # 2. Fetch Items
        if callback: callback(0, 0, f"Fetching items from '{collection_name}'...")
        items = list(self.gateway.get_items_in_collection(collection_id))
        total = len(items)
        
        recovered_rows: List[Dict[str, str]] = []
        
        # 3. Process Items
        for idx, item in enumerate(items):
            if callback: callback(idx + 1, total, f"Scanning: {item.title[:30]}...")
            
            # Find the screening note
            screening_data = self._extract_screening_data(item)
            
            if screening_data:
                # Map to CSV schema
                row = {
                    "key": item.key,
                    "title": item.title,
                    "decision": screening_data.get("decision", "unknown"),
                    "reason": screening_data.get("reason", ""),
                    "criteria": ",".join(screening_data.get("criteria", [])),
                    "timestamp": screening_data.get("timestamp", "")
                }
                recovered_rows.append(row)

        # 4. Write CSV
        if callback: callback(total, total, f"Writing {len(recovered_rows)} records to {output_csv_path}...")
        
        try:
            with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['key', 'title', 'decision', 'reason', 'criteria', 'timestamp']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in recovered_rows:
                    writer.writerow(row)
            return True
        except IOError as e:
            print(f"Error writing CSV: {e}", file=sys.stderr)
            return False

    def _extract_screening_data(self, item: ZoteroItem) -> Optional[Dict]:
        """
        Helper to find and parse the JSON note attached to an item.
        """
        # We need to fetch children for this specific item
        # Ideally, get_items_in_collection should optionally pre-fetch children, 
        # but for now we do a N+1 query (or O(1) if cached).
        # Optimization: The Gateway implementation might be lazy.
        
        children = self.gateway.get_item_children(item.key)
        
        for child in children:
            # Check if it's a note
            if child.get('data', {}).get('itemType') == 'note':
                note_content = child['data'].get('note', '')
                
                # Check for our signature
                if "screening_decision" in note_content:
                    try:
                        # Extract the JSON block
                        # Usually wrapped in <pre> or ```json
                        # Simple robust parser: look for { ... }
                        start = note_content.find('{')
                        end = note_content.rfind('}') + 1
                        if start != -1 and end != -1:
                            json_str = note_content[start:end]
                            # Clean up HTML entities if necessary? 
                            # Usually Zotero API returns clean text or HTML.
                            # Assuming HTML stripping might be needed if it's rich text.
                            # For this MVP, we assume the JSON is parseable.
                            return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
        return None
