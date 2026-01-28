import json
import re
from typing import Dict, List, Optional

from zotero_cli.core.interfaces import ZoteroGateway


class PurgeService:
    """
    Central engine for bulk data removal (attachments, notes, tags).
    Provides safety via dry_run and environment checks.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def _is_offline(self) -> bool:
        # Check if gateway is an instance of SqliteZoteroGateway
        # We use string check to avoid circular imports if any, 
        # or just check the class name.
        return self.gateway.__class__.__name__ == "SqliteZoteroGateway"

    def purge_attachments(self, item_keys: List[str], dry_run: bool = True) -> Dict[str, int]:
        """Deletes all attachments for the given parent item keys."""
        if self._is_offline():
            raise RuntimeError("Offline Veto: PurgeService cannot execute in offline mode.")

        stats = {"deleted": 0, "skipped": 0, "errors": 0}

        for parent_key in item_keys:
            try:
                children = self.gateway.get_item_children(parent_key)
                for child in children:
                    data = child.get("data", child)
                    if data.get("itemType") == "attachment":
                        key = child.get("key") or data.get("key")
                        version = int(data.get("version", 0))
                        if dry_run:
                            stats["skipped"] += 1
                        else:
                            if self.gateway.delete_item(key, version):
                                stats["deleted"] += 1
                            else:
                                stats["errors"] += 1
            except Exception:
                stats["errors"] += 1
        return stats

    def purge_notes(
        self,
        item_keys: List[str],
        sdb_only: bool = False,
        phase: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, int]:
        """
        Deletes notes for the given parent item keys.
        Supports filtering for SDB notes and specific screening phases.
        """
        if self._is_offline():
            raise RuntimeError("Offline Veto: PurgeService cannot execute in offline mode.")

        stats = {"deleted": 0, "skipped": 0, "errors": 0}

        for parent_key in item_keys:
            try:
                children = self.gateway.get_item_children(parent_key)
                for child in children:
                    data = child.get("data", child)
                    if data.get("itemType") == "note":
                        note_content = data.get("note", "")

                        if sdb_only or phase:
                            is_sdb, note_phase = self._parse_sdb_info(note_content)
                            if sdb_only and not is_sdb:
                                continue
                            if phase and note_phase != phase:
                                continue

                        key = child.get("key") or data.get("key")
                        version = int(data.get("version", 0))
                        if dry_run:
                            stats["skipped"] += 1
                        else:
                            if self.gateway.delete_item(key, version):
                                stats["deleted"] += 1
                            else:
                                stats["errors"] += 1
            except Exception:
                stats["errors"] += 1
        return stats

    def purge_tags(
        self, item_keys: List[str], tag_name: Optional[str] = None, dry_run: bool = True
    ) -> Dict[str, int]:
        """
        Removes tags from the given items.
        If tag_name is None, removes all tags.
        """
        if self._is_offline():
            raise RuntimeError("Offline Veto: PurgeService cannot execute in offline mode.")

        stats = {"deleted": 0, "skipped": 0, "errors": 0}

        for key in item_keys:
            try:
                item = self.gateway.get_item(key)
                if not item:
                    stats["errors"] += 1
                    continue

                if not item.tags:
                    continue

                if tag_name:
                    if tag_name not in item.tags:
                        continue
                    new_tags = [t for t in item.tags if t != tag_name]
                else:
                    new_tags = []

                if dry_run:
                    stats["skipped"] += 1
                else:
                    tag_payload = [{"tag": t} for t in new_tags]
                    if self.gateway.update_item_metadata(item.key, item.version, {"tags": tag_payload}):
                        stats["deleted"] += 1
                    else:
                        stats["errors"] += 1
            except Exception:
                stats["errors"] += 1
        return stats

    def purge_item_assets(
        self, item_key: str, types: List[str] = ["files", "notes", "tags"], dry_run: bool = True
    ) -> Dict[str, int]:
        """
        Atomic method to purge specified assets from a single item.
        Types can be 'files', 'notes', 'tags'.
        """
        combined_stats = {"deleted": 0, "skipped": 0, "errors": 0}
        
        # We pass a list of one key
        keys = [item_key]

        if "files" in types:
            s = self.purge_attachments(keys, dry_run=dry_run)
            self._merge_stats(combined_stats, s)
        
        if "notes" in types:
            s = self.purge_notes(keys, dry_run=dry_run)
            self._merge_stats(combined_stats, s)

        if "tags" in types:
            s = self.purge_tags(keys, dry_run=dry_run)
            self._merge_stats(combined_stats, s)

        return combined_stats

    def purge_collection_assets(
        self, col_name: str, types: List[str] = ["files", "notes", "tags"], recursive: bool = False, dry_run: bool = True
    ) -> Dict[str, int]:
        """
        Purges assets from all items in a collection.
        Requires gateway to support collection lookup.
        """
        combined_stats = {"deleted": 0, "skipped": 0, "errors": 0}

        col_id = self.gateway.get_collection_id_by_name(col_name)
        if not col_id:
            combined_stats["errors"] += 1
            return combined_stats

        # Invert recursive to match interface 'top_only'
        # recursive=True -> top_only=False
        # recursive=False -> top_only=True
        items = self.gateway.get_items_in_collection(col_id, top_only=not recursive)
        if not items:
            return combined_stats

        item_keys = [item.key for item in items]

        # Bulk operations where possible for efficiency, 
        # though underlying methods currently iterate one by one.
        if "files" in types:
            s = self.purge_attachments(item_keys, dry_run=dry_run)
            self._merge_stats(combined_stats, s)
        
        if "notes" in types:
            s = self.purge_notes(item_keys, dry_run=dry_run)
            self._merge_stats(combined_stats, s)

        if "tags" in types:
            s = self.purge_tags(item_keys, dry_run=dry_run)
            self._merge_stats(combined_stats, s)

        return combined_stats

    def _merge_stats(self, target: Dict[str, int], source: Dict[str, int]):
        """Helper to merge stats dictionaries."""
        for k in target:
            target[k] += source.get(k, 0)

    def _parse_sdb_info(self, content: str) -> tuple[bool, Optional[str]]:
        """Parses note content for SDB markers and returns (is_sdb, phase)."""
        # Strip HTML if present
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return False, None

        try:
            data = json.loads(json_match.group(0))
            is_sdb = (
                data.get("action") == "screening_decision"
                or "audit_version" in data
                or "sdb_version" in data
            )
            phase = data.get("phase")
            return is_sdb, phase
        except json.JSONDecodeError:
            return False, None
