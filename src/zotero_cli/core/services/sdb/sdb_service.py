from typing import Any, Dict, List, Optional, Tuple

from rich.table import Table

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.children_index import children_by_parent
from zotero_cli.core.utils.sdb_parser import encode_json_note, parse_sdb_note
from zotero_cli.core.utils.terminal_safety import safe_markup

SDB_STATUS_MATCHING = "MATCHING"
SDB_STATUS_CONFLICTING = "CONFLICTING"
SDB_STATUS_UNSCREENED = "UNSCREENED"


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
        return self.inspect_items_sdb([item_key]).get(item_key, [])

    def inspect_items_sdb(self, item_keys: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """The SDB entries of many items, fetched together (Issue #425)."""
        notes = children_by_parent(self.gateway, item_keys, "note")
        return {key: self._sdb_entries(children) for key, children in notes.items()}

    @staticmethod
    def _sdb_entries(children: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

    def classify_decision_agreement(
        self,
        item_keys: List[str],
        entries_by_item: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> str:
        """
        Classifies whether a set of items' recorded SDB screening decisions
        agree: MATCHING (all decided the same way), CONFLICTING (decided
        differently), or UNSCREENED (none has a decision yet). Used to flag
        duplicate groups where independently-screened copies of the same
        paper may disagree - a real SLR audit concern, not just noise.
        """
        if entries_by_item is None:
            entries_by_item = self.inspect_items_sdb(item_keys)
        decisions = {
            entry.get("decision")
            for key in item_keys
            for entry in entries_by_item.get(key, [])
            if entry.get("decision")
        }
        if not decisions:
            return SDB_STATUS_UNSCREENED
        if len(decisions) == 1:
            return SDB_STATUS_MATCHING
        return SDB_STATUS_CONFLICTING

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
                f"[{color}]{safe_markup(decision)}[/{color}]",
                reason,
                e.get("persona", "N/A"),
                e.get("phase", "N/A"),
                e.get("timestamp", "N/A"),
                e.get("audit_version", "N/A"),
            )

        return table

    def edit_sdb_entry(
        self, item_key: str, persona: str, phase: str, updates: Dict[str, Any], dry_run: bool = True
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
        note_content = encode_json_note(new_data)

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

        items = list(self.gateway.get_items_in_collection(col_id))
        entries_by_item = self.inspect_items_sdb([item.key for item in items])

        for item in items:
            for entry in entries_by_item.get(item.key, []):
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
                        note_content = encode_json_note(entry)
                        if self.gateway.update_note(note_key, version, note_content):
                            stats["upgraded"] += 1
                        else:
                            stats["errors"] += 1

        return stats
