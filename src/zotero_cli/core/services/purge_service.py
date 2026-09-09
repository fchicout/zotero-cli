from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ZoteroQuery
from zotero_cli.core.utils.sdb_parser import parse_sdb_note

OFFLINE_ERROR_MSG = "Offline Veto: PurgeService cannot execute in offline mode."

# Below this many parent keys, a single search_items(item_type=...) library
# scan costs more than just looking each one up directly - the batched path
# only pays off once N per-item get_item_children round-trips would exceed
# the cost of the 1-2 scans (Issue #276, same class as #189).
_BATCH_SCAN_THRESHOLD = 2


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

    def _get_children_by_parent(
        self, item_keys: List[str], item_type: str
    ) -> Dict[str, Optional[List[Dict[str, Any]]]]:
        """
        Groups children of the given parent keys by parent, filtered to
        `item_type`. For more than a couple of parents, does one
        `search_items(item_type=...)` library-wide scan instead of one
        `get_item_children` round-trip per parent (Issue #276, same class as
        #189 - mirrors `slr/source_cmd.py`'s `_fetch_pdf_and_note_parent_keys`
        fix). Below that, a per-parent lookup stays cheaper than a full scan.

        A parent key maps to `None` (rather than an empty list) if its
        lookup/the scan itself failed, so callers can distinguish "genuinely
        has no children of this type" from "we couldn't tell" and count it
        as an error like the pre-batching per-item code did.
        """
        by_parent: Dict[str, Optional[List[Dict[str, Any]]]] = {}

        if len(item_keys) > _BATCH_SCAN_THRESHOLD:
            wanted = set(item_keys)
            for key in wanted:
                by_parent[key] = []
            try:
                for item in self.gateway.search_items(ZoteroQuery(item_type=item_type)):
                    parent_key = item.parent_item
                    if parent_key and parent_key in wanted:
                        by_parent[parent_key].append(item.raw_data)  # type: ignore[union-attr]
            except Exception:
                by_parent = dict.fromkeys(wanted, None)
        else:
            for parent_key in item_keys:
                try:
                    children = self.gateway.get_item_children(parent_key)
                    by_parent[parent_key] = [
                        child
                        for child in children
                        if child.get("data", child).get("itemType") == item_type
                    ]
                except Exception:
                    by_parent[parent_key] = None

        return by_parent

    def purge_attachments(self, item_keys: List[str], dry_run: bool = True) -> Dict[str, int]:
        """Deletes all attachments for the given parent item keys."""
        if self._is_offline():
            raise RuntimeError(OFFLINE_ERROR_MSG)

        stats = {"deleted": 0, "skipped": 0, "errors": 0}
        by_parent = self._get_children_by_parent(item_keys, "attachment")

        for parent_key in item_keys:
            children = by_parent.get(parent_key)
            if children is None:
                stats["errors"] += 1
                continue
            try:
                for child in children:
                    data = child.get("data", child)
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
        persona: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, int]:
        """
        Deletes notes for the given parent item keys.
        Supports filtering for SDB notes, specific screening phases, and personas.
        """
        if self._is_offline():
            raise RuntimeError(OFFLINE_ERROR_MSG)

        stats = {"deleted": 0, "skipped": 0, "errors": 0}
        by_parent = self._get_children_by_parent(item_keys, "note")

        for parent_key in item_keys:
            children = by_parent.get(parent_key)
            if children is None:
                stats["errors"] += 1
                continue
            try:
                for child in children:
                    data = child.get("data", child)
                    note_content = data.get("note", "")

                    if sdb_only or phase or persona:
                        is_sdb, note_phase, note_persona = self._parse_sdb_info(note_content)
                        if sdb_only and not is_sdb:
                            continue
                        if phase and note_phase != phase:
                            continue
                        if persona and note_persona != persona:
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
            raise RuntimeError(OFFLINE_ERROR_MSG)

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
                    if self.gateway.update_item_metadata(
                        item.key, item.version, {"tags": tag_payload}
                    ):
                        stats["deleted"] += 1
                    else:
                        stats["errors"] += 1
            except Exception:
                stats["errors"] += 1
        return stats

    def purge_tags_from_collection(self, col_name: str, dry_run: bool = True) -> Dict[str, int]:
        """Specific wrapper for purging tags from a collection."""
        return self.purge_collection_assets(col_name, types=["tags"], dry_run=dry_run)

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
        self,
        col_name: str,
        types: List[str] = ["files", "notes", "tags"],
        recursive: bool = False,
        dry_run: bool = True,
        sdb_only: bool = False,
        phase: Optional[str] = None,
        persona: Optional[str] = None,
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
            s = self.purge_notes(
                item_keys, dry_run=dry_run, sdb_only=sdb_only, phase=phase, persona=persona
            )
            self._merge_stats(combined_stats, s)

        if "tags" in types:
            s = self.purge_tags(item_keys, dry_run=dry_run)
            self._merge_stats(combined_stats, s)

        return combined_stats

    def _merge_stats(self, target: Dict[str, int], source: Dict[str, int]) -> None:
        """Helper to merge stats dictionaries."""
        for k in target:
            target[k] += source.get(k, 0)

    def _parse_sdb_info(self, content: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Parses note content for SDB markers and returns (is_sdb, phase, persona)."""
        data = parse_sdb_note(content)
        if not data:
            return False, None, None
        return True, data.get("phase"), data.get("persona")
