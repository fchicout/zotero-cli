import csv
import json
import sys
from typing import Any, Callable, Dict, List, Optional, cast

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
        if callback:
            callback(0, 0, "Resolving collection ID...")
        collection_id = self.gateway.get_collection_id_by_name(collection_name)
        if not collection_id:
            print(f"Error: Collection '{collection_name}' not found.", file=sys.stderr)
            return False

        # 2. Fetch Items
        if callback:
            callback(0, 0, f"Fetching items from '{collection_name}'...")
        items = list(self.gateway.get_items_in_collection(collection_id))
        total = len(items)

        recovered_rows: List[Dict[str, str]] = []

        # 3. Process Items
        for idx, item in enumerate(items):
            title = item.title if item.title else "Untitled"
            if callback:
                callback(idx + 1, total, f"Scanning: {title[:30]}...")

            try:
                # Find the screening note
                screening_data = self._extract_screening_data(item)

                if screening_data:
                    # Map to CSV schema
                    # SDB v1.1 Mapping:
                    # 'criteria' (CSV) <- 'reason_code' (JSON)
                    # 'reason' (CSV) <- 'reason_text' (JSON)

                    # Try 'reason_code' first (v1.1), fallback to 'criteria' (legacy)
                    criteria_val = screening_data.get("reason_code")
                    if criteria_val is None:
                        criteria_val = screening_data.get("criteria", [])

                    # Try 'reason_text' first, fallback to 'reason'
                    reason_val = screening_data.get("reason_text")
                    if reason_val is None:
                        reason_val = screening_data.get("reason", "")

                    row = {
                        "key": item.key,
                        "title": item.title or "No Title",
                        "decision": screening_data.get("decision", "unknown"),
                        "reason": str(reason_val),
                        "criteria": ",".join(criteria_val) if isinstance(criteria_val, list) else str(criteria_val),
                        "timestamp": screening_data.get("timestamp", "")
                    }
                    recovered_rows.append(row)
            except Exception as e:
                print(f"\n[ERROR] Failed on item {item.key}: {e}", file=sys.stderr)

        # 4. Write CSV
        if not recovered_rows:
            print(f"\nWarning: No screening notes found in '{collection_name}'.", file=sys.stderr)
            return True

        try:
            with open(output_csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["key", "title", "decision", "reason", "criteria", "timestamp"])
                writer.writeheader()
                writer.writerows(recovered_rows)
            return True
        except Exception as e:
            print(f"Error writing CSV file: {e}", file=sys.stderr)
            return False

    def _extract_screening_data(self, item: ZoteroItem) -> Optional[Dict[str, Any]]:
        """Helper to find and parse the screening decision note for an item."""
        try:
            children = self.gateway.get_item_children(item.key)
        except Exception as e:
            print(f"Warning: Failed to fetch children for {item.key}: {e}", file=sys.stderr)
            return None

        for child in children:
            # Check if it's a note
            if child.get('data', {}).get('itemType') == 'note':
                note_content = child['data'].get('note', '')

                # Heuristic 1: Look for JSON-like structure
                start = note_content.find('{')
                end = note_content.rfind('}') + 1

                if start != -1 and end != -1:
                    try:
                        candidate_json = note_content[start:end]
                        # Clean simple HTML entities
                        candidate_json = candidate_json.replace('<br>', '').replace('</p>', '').replace('<p>', '')

                        data = cast(Dict[str, Any], json.loads(candidate_json))

                        # Heuristic 2: Validation
                        if "audit_version" in data or data.get("action") == "screening_decision":
                            return data

                    except json.JSONDecodeError:
                        continue
        return None
