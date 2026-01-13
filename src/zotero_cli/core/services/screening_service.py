from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timezone
import json
import sys

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

class ScreeningService:
    """
    Service responsible for recording screening decisions and managing item movement.
    Provides the core logic for both CLI 'decision' command and TUI 'screen' mode.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def record_decision(
        self,
        item_key: str,
        decision: str,  # 'INCLUDE' or 'EXCLUDE'
        code: str,
        reason: Optional[str] = None,
        source_collection: Optional[str] = None,
        target_collection: Optional[str] = None,
        agent: str = "zotero-cli",
        persona: str = "unknown",
        phase: str = "title_abstract"
    ) -> bool:
        """
        Records a screening decision for a Zotero item.
        1. Creates a child note with the decision metadata (JSON).
        2. Optionally moves the item from source to target collection.
        """
        decision_upper = decision.upper()
        if decision_upper not in ["INCLUDE", "EXCLUDE"]:
            print(f"Error: Invalid decision '{decision_upper}'. Must be INCLUDE or EXCLUDE.", file=sys.stderr)
            return False

        # Map internal decision to SDB decision
        sdb_decision = "accepted" if decision_upper == "INCLUDE" else "rejected"

        # 1. Create the Audit Note using SDB v1.1
        decision_data = {
            "audit_version": "1.1",
            "decision": sdb_decision,
            "reason_code": [code.strip() for code in code.split(',')] if code else [],
            "reason_text": reason if reason else "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "persona": persona,
            "phase": phase,
            "action": "screening_decision" # Keep for backward compatibility/filtering
        }
        
        note_content = f"<div>{json.dumps(decision_data, indent=2)}</div>"
        
        # We need a way to create a note in the gateway. 
        # Checking ZoteroAPIClient for 'create_note' or similar.
        # It seems we have 'upload_attachment' but not a generic 'create_note' for text.
        # Wait, I see 'create_item' in zotero_api.py. I might need to add 'create_note'.
        
        # Let's add a create_note method to the gateway if it's missing.
        # I'll check ZoteroAPIClient again.
        
        success = self.gateway.create_note(item_key, note_content)
        if not success:
            print(f"Error: Failed to create audit note for item {item_key}.", file=sys.stderr)
            return False

        # 2. Collection Movement (Optional)
        if source_collection and target_collection:
            # Fetch item to get current collections
            item = self.gateway.get_item(item_key)
            if not item:
                print(f"Error: Item {item_key} not found for movement.", file=sys.stderr)
                return False
            
            source_id = self.gateway.get_collection_id_by_name(source_collection)
            target_id = self.gateway.get_collection_id_by_name(target_collection)
            
            if not source_id or not target_id:
                print(f"Error: Source or Target collection not found.", file=sys.stderr)
                return False
            
            # Update collections list
            new_collections = [c for c in item.collections if c != source_id]
            if target_id not in new_collections:
                new_collections.append(target_id)
            
            move_success = self.gateway.update_item_collections(item_key, item.version, new_collections)
            if not move_success:
                print(f"Warning: Decision recorded but failed to move item {item_key}.", file=sys.stderr)
        
        return True

    def get_pending_items(self, collection_name: str) -> List[ZoteroItem]:
        """
        Fetches items from a collection that do NOT yet have a screening decision note.
        """
        col_id = self.gateway.get_collection_id_by_name(collection_name)
        if not col_id:
            return []
        
        all_items = self.gateway.get_items_in_collection(col_id)
        pending = []
        
        for item in all_items:
            # Check if item has a decision note
            children = self.gateway.get_item_children(item.key)
            has_decision = False
            for child in children:
                if child.get('itemType') == 'note':
                    content = child.get('note', '')
                    if 'screening_decision' in content:
                        has_decision = True
                        break
            
            if not has_decision:
                pending.append(item)
                
        return pending
