import csv
import io
import json
from typing import Any, Dict, List, Optional

from zotero_cli.core.services.duplicate_service import DuplicateOccurrence
from zotero_cli.core.services.merge_service import (
    MERGE_PLAN_SCHEMA_VERSION,
    MergeDecision,
    MergePlan,
    MergePlanEntry,
)

CSV_FIELDNAMES = [
    "group_id",
    "match_type",
    "identifier",
    "key",
    "collection_id",
    "title",
    "role",
    "reason",
]


def serialize_plan_to_csv(plan: MergePlan) -> str:
    """
    One row per occurrence, `group_id` repeated across a group's rows so it
    opens cleanly in a spreadsheet. `role`/`reason` are blank for an
    undecided group - fill in `role` (MASTER/MERGE/KEEP) per row and `reason`
    on any one row per group, then feed the file back through
    `item merge --from-plan`.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    for entry in plan.entries:
        decision = entry.decision
        for occ in entry.occurrences:
            role = ""
            reason = ""
            if decision:
                reason = decision.reason
                if occ.key == decision.master_key:
                    role = "MASTER"
                elif occ.key in decision.merge_keys:
                    role = "MERGE"
                elif occ.key in decision.keep_keys:
                    role = "KEEP"
            writer.writerow(
                {
                    "group_id": entry.group_id,
                    "match_type": entry.match_type,
                    "identifier": entry.identifier,
                    "key": occ.key,
                    "collection_id": occ.collection_id,
                    "title": occ.title or "",
                    "role": role,
                    "reason": reason,
                }
            )
    return buffer.getvalue()


def parse_plan_from_csv(text: str) -> MergePlan:
    """
    Structural parse only - does not validate completeness (a group with no
    `role` filled in yet simply gets `decision=None`). Validation happens at
    `MergeService.execute_plan` time.
    """
    rows = list(csv.DictReader(io.StringIO(text)))
    entries_by_group: Dict[str, MergePlanEntry] = {}
    reasons_by_group: Dict[str, str] = {}
    roles_by_group: Dict[str, Dict[str, str]] = {}

    for row in rows:
        group_id = row["group_id"]
        entry = entries_by_group.get(group_id)
        if entry is None:
            entry = MergePlanEntry(
                group_id=group_id,
                match_type=row["match_type"],
                identifier=row["identifier"],
                occurrences=[],
            )
            entries_by_group[group_id] = entry
            roles_by_group[group_id] = {}

        entry.occurrences.append(
            DuplicateOccurrence(
                key=row["key"],
                collection_id=row["collection_id"],
                title=row["title"] or None,
            )
        )
        role = (row.get("role") or "").strip().upper()
        if role:
            roles_by_group[group_id][row["key"]] = role
        reason = (row.get("reason") or "").strip()
        if reason and not reasons_by_group.get(group_id):
            reasons_by_group[group_id] = reason

    for group_id, entry in entries_by_group.items():
        roles = roles_by_group[group_id]
        if not roles:
            continue  # No role filled in for any row yet - stays undecided.
        master_keys = [k for k, r in roles.items() if r == "MASTER"]
        if len(master_keys) != 1:
            continue  # Malformed/incomplete - leave undecided, execute_plan will report it.
        entry.decision = MergeDecision(
            master_key=master_keys[0],
            merge_keys=[k for k, r in roles.items() if r == "MERGE"],
            keep_keys=[k for k, r in roles.items() if r == "KEEP"],
            reason=reasons_by_group.get(group_id, ""),
        )

    return MergePlan(entries=list(entries_by_group.values()))


def serialize_plan_to_json(
    plan: MergePlan, sdb_history: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> str:
    """
    `sdb_history` (key -> full parsed SDB entries, e.g. from
    `SDBService.inspect_item_sdb`) is informational only - it gives a
    consumer like Corbenic-SLR's screening UI the full decision/provenance
    history per occurrence to show a researcher, not a rollup label. It is
    not read back by `parse_plan_from_json`.
    """
    sdb_history = sdb_history or {}
    payload = {
        "version": plan.version,
        "entries": [
            {
                "group_id": entry.group_id,
                "match_type": entry.match_type,
                "identifier": entry.identifier,
                "occurrences": [
                    {
                        "key": occ.key,
                        "collection_id": occ.collection_id,
                        "title": occ.title,
                        "sdb_history": sdb_history.get(occ.key, []),
                    }
                    for occ in entry.occurrences
                ],
                "decision": (
                    {
                        "master_key": entry.decision.master_key,
                        "merge_keys": entry.decision.merge_keys,
                        "keep_keys": entry.decision.keep_keys,
                        "reason": entry.decision.reason,
                    }
                    if entry.decision
                    else None
                ),
            }
            for entry in plan.entries
        ],
    }
    return json.dumps(payload, indent=2)


def parse_plan_from_json(text: str) -> MergePlan:
    data = json.loads(text)
    entries = []
    for raw_entry in data.get("entries", []):
        raw_decision = raw_entry.get("decision")
        decision = (
            MergeDecision(
                master_key=raw_decision["master_key"],
                merge_keys=list(raw_decision.get("merge_keys", [])),
                keep_keys=list(raw_decision.get("keep_keys", [])),
                reason=raw_decision.get("reason", ""),
            )
            if raw_decision
            else None
        )
        entries.append(
            MergePlanEntry(
                group_id=raw_entry["group_id"],
                match_type=raw_entry["match_type"],
                identifier=raw_entry["identifier"],
                occurrences=[
                    DuplicateOccurrence(
                        key=occ["key"], collection_id=occ["collection_id"], title=occ.get("title")
                    )
                    for occ in raw_entry.get("occurrences", [])
                ],
                decision=decision,
            )
        )
    return MergePlan(version=data.get("version", MERGE_PLAN_SCHEMA_VERSION), entries=entries)
