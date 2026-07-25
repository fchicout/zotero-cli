from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.duplicate_service import (
    DuplicateFinder,
    DuplicateGroup,
    DuplicateOccurrence,
)
from zotero_cli.core.services.merge_service import (
    MergeDecision,
    MergePlan,
    MergePlanEntry,
    MergeService,
    PlanExecutionResult,
)
from zotero_cli.core.services.sdb.sdb_service import (
    SDB_STATUS_CONFLICTING,
    SDB_STATUS_MATCHING,
    SDB_STATUS_UNSCREENED,
    SDBService,
)
from zotero_cli.core.services.slr.orchestrator import SLROrchestrator


@dataclass
class OccurrenceScreening:
    """One duplicate group occurrence, plus its recorded SDB decisions (if any)."""

    key: str
    collection_id: str
    title: Optional[str] = None
    decisions: List[str] = field(default_factory=list)


@dataclass
class ClassifiedDuplicateGroup:
    """A DuplicateGroup enriched with its SDB screening-decision agreement status."""

    match_type: str
    identifier: str
    sdb_status: str  # MATCHING / CONFLICTING / UNSCREENED (see sdb_service.py)
    occurrences: List[OccurrenceScreening] = field(default_factory=list)


class SLRDedupeService:
    """
    SLR-specific duplicate reconciliation layer on top of the generic
    DuplicateFinder/MergeService primitives (Issues #152/#155/#156).

    A rigorous SLR can't just auto-merge every detected duplicate: the same
    paper can arrive as separate items from separate sources and get
    screened independently before anyone notices they're duplicates,
    producing genuinely conflicting recorded decisions. This service
    classifies each duplicate group by SDB-decision agreement (MATCHING /
    CONFLICTING / UNSCREENED), auto-fills a MergePlan decision for the safe
    cases, and leaves CONFLICTING groups undecided - the plan itself becomes
    the reconciliation surface for a human or Corbenic-SLR to resolve.
    Physical consolidation is delegated entirely to MergeService; this
    service only adds a richer SDB audit note on top once a merge lands.

    Directly importable/callable: typed dataclasses, no stdout side effects,
    narrow constructor deps - this is the code path Corbenic-SLR's screening
    UI calls directly (per Issue #153's API-hygiene requirement).
    """

    def __init__(
        self,
        gateway: ZoteroGateway,
        duplicate_finder: DuplicateFinder,
        merge_service: MergeService,
        sdb_service: SDBService,
        orchestrator: SLROrchestrator,
    ):
        self.gateway = gateway
        self.duplicate_finder = duplicate_finder
        self.merge_service = merge_service
        self.sdb_service = sdb_service
        self.orchestrator = orchestrator
        self.warnings: List[str] = []

    def source_collection_ids(self) -> List[str]:
        """
        Every collection in the SLR source tree: `raw_*` parents plus their
        direct phase subfolders. Items move between the parent and its
        subfolders as screening progresses (`slr promote`/`slr reconcile`),
        so scoping to the parent alone would miss items already promoted.
        """
        cols = self.gateway.get_all_collections()
        raw_parent_keys = {
            c["key"] for c in cols if c.get("data", {}).get("name", "").startswith("raw_")
        }
        ids = list(raw_parent_keys)
        for c in cols:
            if c.get("data", {}).get("parentCollection") in raw_parent_keys:
                ids.append(c["key"])
        return ids

    def find_and_classify(
        self, collection_ids: Optional[List[str]] = None
    ) -> List[ClassifiedDuplicateGroup]:
        """
        Detects duplicates (exact + fuzzy tiers, via DuplicateFinder - no
        forked matching logic) scoped to `collection_ids`, or the whole SLR
        source tree if omitted, and classifies each group by SDB
        screening-decision agreement.
        """
        scope = collection_ids if collection_ids is not None else self.source_collection_ids()
        groups = self.duplicate_finder.compare_collections(scope)
        self.warnings = list(self.duplicate_finder.warnings)
        return [self._classify(g) for g in groups]

    def _classify(self, group: DuplicateGroup) -> ClassifiedDuplicateGroup:
        occurrences = []
        all_decisions: set = set()
        for occ in group.occurrences:
            entries = self.sdb_service.inspect_item_sdb(occ.key)
            decisions: List[str] = [str(e["decision"]) for e in entries if e.get("decision")]
            all_decisions.update(decisions)
            occurrences.append(
                OccurrenceScreening(
                    key=occ.key,
                    collection_id=occ.collection_id,
                    title=occ.title,
                    decisions=decisions,
                )
            )

        if not all_decisions:
            status = SDB_STATUS_UNSCREENED
        elif len(all_decisions) == 1:
            status = SDB_STATUS_MATCHING
        else:
            status = SDB_STATUS_CONFLICTING

        return ClassifiedDuplicateGroup(
            match_type=group.match_type,
            identifier=group.identifier,
            sdb_status=status,
            occurrences=occurrences,
        )

    def build_reconciliation_plan(self, groups: List[ClassifiedDuplicateGroup]) -> MergePlan:
        """
        Wraps classified groups into a MergePlan: MATCHING/UNSCREENED groups
        get an auto-filled decision (the lexicographically-first occurrence
        key becomes master, purely for determinism - MergeService resolves
        any scalar field conflict to whichever value the chosen master
        already has, so the specific pick doesn't matter methodologically).
        CONFLICTING groups are left undecided - a human or Corbenic-SLR must
        resolve those, e.g. via an exported plan file and `item merge
        --from-plan`.
        """
        entries = []
        for g in groups:
            occ_keys = sorted(occ.key for occ in g.occurrences)
            decision = None
            if g.sdb_status != SDB_STATUS_CONFLICTING and len(occ_keys) > 1:
                master_key, *merge_keys = occ_keys
                decision = MergeDecision(
                    master_key=master_key,
                    merge_keys=merge_keys,
                    reason=f"SLR dedupe auto-resolution: SDB decisions {g.sdb_status.lower()}.",
                )
            entries.append(
                MergePlanEntry(
                    group_id=f"{g.match_type}:{g.identifier}",
                    match_type=g.match_type,
                    identifier=g.identifier,
                    occurrences=[
                        DuplicateOccurrence(key=o.key, collection_id=o.collection_id, title=o.title)
                        for o in g.occurrences
                    ],
                    decision=decision,
                )
            )
        return MergePlan(entries=entries)

    def execute_reconciliation(self, plan: MergePlan, dry_run: bool = True) -> PlanExecutionResult:
        """
        Delegates physical consolidation entirely to
        `MergeService.execute_plan` (all-or-nothing across whatever entries
        `plan` contains - callers should submit only the already-resolved
        subset of a mixed plan, since CONFLICTING groups are meant to stay
        outside of automatic execution). On a real, successful execution,
        additionally writes a richer SDB reconciliation note per merged
        duplicate via `SLROrchestrator`, capturing every folded occurrence's
        own SDB decisions and source collection.

        Provenance is captured *before* `execute_plan` runs: a successful
        merge permanently deletes the duplicate items, so their SDB notes
        would no longer be readable afterwards.
        """
        provenance_by_group: Dict[str, List[Dict[str, Any]]] = {}
        if not dry_run:
            for entry in plan.entries:
                if entry.decision is None or not entry.decision.merge_keys:
                    continue
                provenance_by_group[entry.group_id] = [
                    {
                        "key": occ.key,
                        "collection_id": occ.collection_id,
                        "decisions": [
                            e.get("decision")
                            for e in self.sdb_service.inspect_item_sdb(occ.key)
                            if e.get("decision")
                        ],
                    }
                    for occ in entry.occurrences
                ]

        result = self.merge_service.execute_plan(plan, dry_run=dry_run)

        if not dry_run and result.success:
            for entry in plan.entries:
                decision = entry.decision
                if decision is None or not decision.merge_keys:
                    continue
                provenance = provenance_by_group.get(entry.group_id, [])
                for dup_key in decision.merge_keys:
                    self.orchestrator.record_duplicate_resolution(
                        item_key=decision.master_key,
                        duplicate_key=dup_key,
                        reason=decision.reason
                        or f"SLR dedupe reconciliation ({entry.match_type}:{entry.identifier})",
                        provenance=provenance,
                    )

        return result
