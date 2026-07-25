from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import ItemRepository, NoteRepository
from zotero_cli.core.services.duplicate_service import DuplicateGroup, DuplicateOccurrence
from zotero_cli.core.zotero_item import ZoteroItem

MERGE_PLAN_SCHEMA_VERSION = "1.0"


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


@dataclass
class MergeDecision:
    """
    A resolved decision for one MergePlanEntry (duplicate group): which
    occurrence becomes the master, which fold into it, which are left alone
    (a false positive from detection - not actually a duplicate), and why.

    `reason` is required (non-empty) for a decision to count as resolved,
    regardless of whether the group had any SDB-decision conflict - this
    keeps plan *execution* fully agnostic of what "conflicting" even means
    (that judgment belongs to whichever producer built the plan, e.g. an
    SLR-aware caller), while still capturing rigor whenever one is behind it.
    """

    master_key: str
    merge_keys: List[str] = field(default_factory=list)
    keep_keys: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class MergePlanEntry:
    """One duplicate group within a MergePlan, plus its (optional) decision."""

    group_id: str
    match_type: str
    identifier: str
    occurrences: List[DuplicateOccurrence] = field(default_factory=list)
    decision: Optional[MergeDecision] = None


@dataclass
class MergePlan:
    """
    A batch of duplicate groups awaiting (or carrying) merge decisions.

    Built from `DuplicateFinder`'s detection output via `MergeService.build_plan`.
    Consumed either directly as Python objects (Corbenic-SLR: build it, let the
    caller fill in `entries[i].decision` in-memory, then call `execute_plan` -
    no serialization involved) or round-tripped through CSV/JSON for the plain
    CLI/shell workflow (see `merge_plan_io.py`).
    """

    version: str = MERGE_PLAN_SCHEMA_VERSION
    entries: List[MergePlanEntry] = field(default_factory=list)


@dataclass
class PlanExecutionResult:
    """
    Outcome of `MergeService.execute_plan`. `success=False` with a non-empty
    `errors` and empty `group_results` means the plan failed *completeness*
    validation - nothing was written for any group, not just the invalid one
    (partial execution of an incompletely-reviewed plan isn't attempted).
    """

    success: bool
    dry_run: bool
    group_results: List[MergeResult] = field(default_factory=list)
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

    @staticmethod
    def build_plan(groups: List[DuplicateGroup]) -> MergePlan:
        """
        Wraps detection output (e.g. from `DuplicateFinder.compare_collections`)
        into an undecided MergePlan. Pure/no repository access - `group_id` is
        deterministic (`match_type:identifier`) so the same detection result
        produces stable IDs across re-runs.
        """
        return MergePlan(
            entries=[
                MergePlanEntry(
                    group_id=f"{g.match_type}:{g.identifier}",
                    match_type=g.match_type,
                    identifier=g.identifier,
                    occurrences=list(g.occurrences),
                )
                for g in groups
            ]
        )

    def execute_plan(self, plan: MergePlan, dry_run: bool = True) -> PlanExecutionResult:
        """
        Executes every resolved group in `plan`. Refuses to write anything at
        all - not even for otherwise-valid groups - if any entry is missing a
        decision or fails validation (completeness is all-or-nothing, matching
        the "only update Zotero once the full review session is complete"
        model this plan format is designed for).

        Bulk merges default every conflicting scalar field to the chosen
        master's own current value rather than prompting per-field the way the
        single-group `merge()` CLI path does: the human/producer already made
        the real decision by choosing which occurrence is master, so this
        doesn't re-litigate it - it's simply not appropriate to prompt
        interactively inside a batch/programmatic execution path.

        Each group's underlying `merge()` call re-fetches items (and their
        current version) fresh at execution time, so a stale plan can't
        silently clobber an item that changed since the plan was built.
        """
        validation_errors: List[str] = []
        for entry in plan.entries:
            validation_errors.extend(self._validate_entry(entry))
        if validation_errors:
            return PlanExecutionResult(success=False, dry_run=dry_run, errors=validation_errors)

        group_results: List[MergeResult] = []
        overall_success = True
        for entry in plan.entries:
            decision = entry.decision
            if decision is None:
                continue  # Unreachable: _validate_entry above already rejected this.
            if not decision.merge_keys:
                continue  # Nothing to merge in this group (e.g. all KEEP).

            master_item = self.item_repo.get_item(decision.master_key)
            if master_item is None:
                overall_success = False
                group_results.append(
                    MergeResult(
                        success=False,
                        dry_run=dry_run,
                        master_key=decision.master_key,
                        errors=[f"Master item '{decision.master_key}' not found."],
                    )
                )
                continue

            field_resolutions = {
                attr: getattr(master_item, attr)
                for attr in self.MERGEABLE_FIELDS
                if getattr(master_item, attr)
            }
            result = self.merge(
                decision.master_key,
                decision.merge_keys,
                field_resolutions=field_resolutions,
                dry_run=dry_run,
            )
            group_results.append(result)
            if not result.success:
                overall_success = False

        return PlanExecutionResult(
            success=overall_success, dry_run=dry_run, group_results=group_results
        )

    def _validate_entry(self, entry: MergePlanEntry) -> List[str]:
        decision = entry.decision
        if decision is None:
            return [f"Group '{entry.group_id}' has no decision."]
        if not decision.reason.strip():
            return [f"Group '{entry.group_id}' decision has no reason."]

        occurrence_keys = {occ.key for occ in entry.occurrences}
        if decision.master_key not in occurrence_keys:
            return [
                f"Group '{entry.group_id}': master_key '{decision.master_key}' is not "
                "one of this group's occurrences."
            ]

        assigned = {decision.master_key, *decision.merge_keys, *decision.keep_keys}
        missing = occurrence_keys - assigned
        if missing:
            return [
                f"Group '{entry.group_id}': occurrence(s) {sorted(missing)} have no "
                "role (must be the master, in merge_keys, or in keep_keys)."
            ]
        extra = assigned - occurrence_keys
        if extra:
            return [
                f"Group '{entry.group_id}': decision references key(s) {sorted(extra)} "
                "that aren't occurrences of this group."
            ]
        overlap = set(decision.merge_keys) & set(decision.keep_keys)
        if overlap:
            return [
                f"Group '{entry.group_id}': key(s) {sorted(overlap)} are in both "
                "merge_keys and keep_keys."
            ]
        return []

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
