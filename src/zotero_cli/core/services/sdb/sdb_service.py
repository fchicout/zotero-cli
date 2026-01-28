from typing import Any, Dict, List, Optional, Tuple

from rich.table import Table

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.utils.sdb_parser import parse_sdb_note


class SDBService:
    """
    Management service for the Screening Database (SDB) layer embedded in Zotero notes.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def inspect_item_sdb(self, item_key: str) -> List[Dict[str, Any]]:
        """
        Retrieves all valid SDB entries for an item.
        Returns a list of parsed dictionaries.
        """
        children = self.gateway.get_item_children(item_key)
        sdb_entries = []

        for child in children:
            data = child.get("data", child)
            if data.get("itemType") == "note":
                content = data.get("note", "")
                parsed = parse_sdb_note(content)
                if parsed:
                    # Enrich with metadata needed for display/edit
                    parsed["_note_key"] = child.get("key") or data.get("key")
                    parsed["_note_version"] = int(child.get("version") or data.get("version") or 0)
                    sdb_entries.append(parsed)
        
        return sdb_entries

    def build_inspect_table(self, item_key: str, entries: List[Dict[str, Any]]) -> Table:
        table = Table(title=f"SDB Inspect: {item_key}")
        table.add_column("Decision")
        table.add_column("Criteria/Reason")
        table.add_column("Persona", style="cyan")
        table.add_column("Phase", style="magenta")
        table.add_column("Timestamp", style="dim")
        table.add_column("Version", style="dim")

        for e in entries:
            decision = e.get("decision", "N/A")
            color = "green" if decision == "accepted" else "red"
            
            reason = ", ".join(e.get("reason_code", []))
            if e.get("reason_text"):
                reason += f" ({e['reason_text'][:30]}...)"
            
            table.add_row(
                f"[{color}]{decision}[/{color}]",
                reason,
                e.get("persona", "N/A"),
                e.get("phase", "N/A"),
                e.get("timestamp", "N/A"),
                e.get("audit_version", "N/A")
            )
        
        return table

    def edit_sdb_entry(
        self,
        item_key: str,
        persona: str,
        phase: str,
        updates: Dict[str, Any],
        dry_run: bool = True
    ) -> Tuple[bool, str]:
        """
        Surgically edits an SDB entry matching the persona/phase pair.
        Returns (success, message).
        """
        entries = self.inspect_item_sdb(item_key)
        target = None
        
        for e in entries:
            if e.get("persona") == persona and e.get("phase") == phase:
                target = e
                break
        
        if not target:
            return False, f"No SDB entry found for persona='{persona}' and phase='{phase}'."

        # Apply updates to a copy
        import json
        new_data = target.copy()
        # Remove internal keys before saving
        note_key = new_data.pop("_note_key")
        version = new_data.pop("_note_version")
        
        # Apply changes
        for k, v in updates.items():
            if v is not None:
                new_data[k] = v

        if dry_run:
            diff = []
            for k in updates:
                if updates[k] is not None:
                    diff.append(f"{k}: {target.get(k)} -> {updates[k]}")
            return True, f"[DRY RUN] Would update note {note_key}:\n" + "\n".join(diff)

        # Write back
        # We need to wrap it in div as per standard, or rely on existing format?
        # Ideally we standardized on <div>{json}</div> in record_decision.
        # Let's match that format.
        note_content = f"<div>{json.dumps(new_data, indent=2)}</div>"
        
        if self.gateway.update_note(note_key, version, note_content):
            return True, f"Successfully updated SDB entry in note {note_key}."
        else:
            return False, f"Failed to update note {note_key} via API."

    def upgrade_sdb_entries(self, collection_name: str, dry_run: bool = True) -> Dict[str, int]:
        """
        Scans a collection for legacy SDB notes (audit_version < 1.2) and upgrades them.
        """
        stats = {"scanned": 0, "upgraded": 0, "skipped": 0, "errors": 0}
        
        col_id = self.gateway.get_collection_id_by_name(collection_name)
        if not col_id:
            stats["errors"] += 1
            return stats

        items = self.gateway.get_items_in_collection(col_id)
        
        import json
        
        for item in items:
            entries = self.inspect_item_sdb(item.key)
            for entry in entries:
                stats["scanned"] += 1
                current_ver = entry.get("audit_version", "1.0")
                
                if current_ver < "1.2":
                    # Upgrade Logic
                    entry["audit_version"] = "1.2"
                    
                    # Map legacy fields if necessary
                    # e.g., 'comment' -> 'reason_text'
                    if "comment" in entry and "reason_text" not in entry:
                        entry["reason_text"] = entry.pop("comment")
                    
                    if dry_run:
                        stats["skipped"] += 1
                    else:
                        note_key = entry.pop("_note_key")
                        version = entry.pop("_note_version")
                        note_content = f"<div>{json.dumps(entry, indent=2)}</div>"
                        if self.gateway.update_note(note_key, version, note_content):
                            stats["upgraded"] += 1
                        else:
                            stats["errors"] += 1
        
        return stats
