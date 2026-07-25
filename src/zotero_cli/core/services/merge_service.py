from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import ItemRepository, NoteRepository
from zotero_cli.core.zotero_item import ZoteroItem


@dataclass
class FieldConflict:
    """A scalar field where the master and/or duplicates disagree on a value."""

    field_name: str
    values: Dict[str, Optional[str]] = field(default_factory=dict)


@dataclass
class MergeResult:
    """
    Outcome of a merge (or, when `dry_run=True`, a preview of what a merge
    would do). `success=False` with a non-empty `unresolved_conflicts` means
    nothing was written - the caller must resolve those fields and call
    `merge()` again with `field_resolutions` covering them.
    """

    success: bool
    dry_run: bool
    master_key: str
    merged_keys: List[str] = field(default_factory=list)
    notes_moved: int = 0
    attachments_moved: int = 0
    tags_added: int = 0
    collections_added: int = 0
    field_resolutions_applied: Dict[str, str] = field(default_factory=dict)
    unresolved_conflicts: List[FieldConflict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class MergeService:
    """
    Generic, SLR-independent primitive for merging duplicate Zotero items into
    one survivor: unions tags/collections, re-parents notes/attachments onto
    the master, and hard-deletes the (now emptied) duplicates once any
    conflicting scalar fields have an explicit resolution.

    The Web API only exposes a hard, permanent DELETE - there is no
    documented soft-delete/relations-based merge the way Zotero Desktop's
    internal "equate item IDs" mechanism implies (see Issue #145). Retiring
    the losing duplicates here is therefore permanent and non-reversible,
    and cannot preserve external citation-plugin references pointing at
    their keys the way Desktop's internal mechanism does. Callers (CLI or
    otherwise) must make that plain to the user before calling with
    `dry_run=False`.

    Directly importable/callable: no stdout side effects, typed dataclass
    inputs/outputs, narrow (ItemRepository/NoteRepository) constructor deps.
    """

    # Scalar ZoteroItem attributes this service can detect conflicts on and
    # write a resolution back for, mapped to their raw Zotero JSON field name.
    # `arxiv_id` is deliberately excluded: it's parsed out of the free-text
    # `extra` field, not a field of its own, so there's no clean raw key to
    # write a resolved value back to without risking clobbering unrelated
    # `extra` content.
    MERGEABLE_FIELDS: Dict[str, str] = {
        "title": "title",
        "date": "date",
        "doi": "DOI",
        "isbn": "ISBN",
        "url": "url",
        "abstract": "abstractNote",
    }

    def __init__(self, item_repo: ItemRepository, note_repo: NoteRepository):
        self.item_repo = item_repo
        self.note_repo = note_repo

    def detect_conflicts(self, master_key: str, duplicate_keys: List[str]) -> List[FieldConflict]:
        """
        Read-only: for each mergeable field, reports a conflict if more than
        one distinct non-empty value exists across the master and duplicates.
        """
        items = self._fetch_items(master_key, duplicate_keys)
        conflicts = []
        for attr in self.MERGEABLE_FIELDS:
            values: Dict[str, Optional[str]] = {}
            distinct = set()
            for key, item in items.items():
                if item is None:
                    continue
                value = getattr(item, attr, None)
                values[key] = value
                if value:
                    distinct.add(value)
            if len(distinct) > 1:
                conflicts.append(FieldConflict(field_name=attr, values=values))
        return conflicts

    def merge(
        self,
        master_key: str,
        duplicate_keys: List[str],
        field_resolutions: Optional[Dict[str, str]] = None,
        dry_run: bool = True,
    ) -> MergeResult:
        field_resolutions = field_resolutions or {}
        result = MergeResult(success=False, dry_run=dry_run, master_key=master_key)

        items = self._fetch_items(master_key, duplicate_keys)
        master = items.get(master_key)
        if master is None:
            result.errors.append(f"Master item '{master_key}' not found.")
            return result

        missing = [k for k in duplicate_keys if items.get(k) is None]
        if missing:
            result.errors.append(f"Duplicate item(s) not found: {', '.join(missing)}")
            return result

        duplicates: List[ZoteroItem] = [
            item for item in (items[k] for k in duplicate_keys) if item is not None
        ]

        mismatched_types = sorted({d.item_type for d in duplicates if d.item_type != master.item_type})
        if mismatched_types:
            result.errors.append(
                f"Item type mismatch: master '{master_key}' is '{master.item_type}', "
                f"found {mismatched_types} among duplicates. Merge requires matching "
                "item types (same rule Zotero Desktop enforces)."
            )
            return result

        conflicts = self.detect_conflicts(master_key, duplicate_keys)
        unresolved = [c for c in conflicts if c.field_name not in field_resolutions]
        if unresolved:
            result.unresolved_conflicts = unresolved
            result.errors.append(
                f"{len(unresolved)} field conflict(s) require an explicit resolution "
                "before this merge can proceed."
            )
            return result

        merged_tags = set(master.tags)
        merged_collections = set(master.collections)
        for d in duplicates:
            merged_tags |= set(d.tags)
            merged_collections |= set(d.collections)
        new_tags = merged_tags - set(master.tags)
        new_collections = merged_collections - set(master.collections)

        notes_to_move: List[Dict[str, Any]] = []
        attachments_to_move: List[Dict[str, Any]] = []
        for d in duplicates:
            for child in self.item_repo.get_item_children(d.key):
                data = child.get("data", child)
                child_type = data.get("itemType")
                child_key = child.get("key") or data.get("key")
                child_version = int(data.get("version") or child.get("version") or 0)
                if child_type == "note":
                    notes_to_move.append(
                        {"key": child_key, "version": child_version, "note": data.get("note", "")}
                    )
                elif child_type == "attachment":
                    attachments_to_move.append({"key": child_key, "version": child_version})

        result.field_resolutions_applied = dict(field_resolutions)
        result.tags_added = len(new_tags)
        result.collections_added = len(new_collections)

        if dry_run:
            result.success = True
            result.merged_keys = duplicate_keys
            result.notes_moved = len(notes_to_move)
            result.attachments_moved = len(attachments_to_move)
            return result

        master_updates: Dict[str, Any] = {}
        if new_tags:
            master_updates["tags"] = [{"tag": t} for t in sorted(merged_tags)]
        if new_collections:
            master_updates["collections"] = sorted(merged_collections)
        for field_name, value in field_resolutions.items():
            raw_key = self.MERGEABLE_FIELDS.get(field_name)
            if raw_key:
                master_updates[raw_key] = value

        if master_updates:
            if not self.item_repo.update_item(master.key, master.version, master_updates):
                result.errors.append(f"Failed to update master item '{master.key}'.")
                return result

        moved_notes = 0
        for note in notes_to_move:
            if self.note_repo.update_note(
                note["key"], note["version"], note["note"], parent_item_key=master_key
            ):
                moved_notes += 1
            else:
                result.errors.append(f"Failed to move note '{note['key']}' to master.")

        moved_attachments = 0
        if attachments_to_move:
            payload = [
                {"key": a["key"], "version": a["version"], "parentItem": master_key}
                for a in attachments_to_move
            ]
            if self.item_repo.update_items(payload):
                moved_attachments = len(attachments_to_move)
            else:
                result.errors.append("Failed to move one or more attachments to master.")

        deleted_keys = []
        for d in duplicates:
            if self.item_repo.delete_item(d.key, d.version):
                deleted_keys.append(d.key)
            else:
                result.errors.append(f"Failed to delete duplicate item '{d.key}' after merge.")

        result.merged_keys = deleted_keys
        result.notes_moved = moved_notes
        result.attachments_moved = moved_attachments
        result.success = not result.errors
        return result

    def _fetch_items(
        self, master_key: str, duplicate_keys: List[str]
    ) -> Dict[str, Optional[ZoteroItem]]:
        return {key: self.item_repo.get_item(key) for key in [master_key, *duplicate_keys]}
