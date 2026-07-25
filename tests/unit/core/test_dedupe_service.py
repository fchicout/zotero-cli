from unittest.mock import Mock

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.duplicate_service import (
    DuplicateFinder,
    DuplicateGroup,
    DuplicateOccurrence,
)
from zotero_cli.core.services.merge_service import (
    MergePlan,
    MergePlanEntry,
    MergeResult,
    MergeService,
    PlanExecutionResult,
)
from zotero_cli.core.services.sdb.sdb_service import SDBService
from zotero_cli.core.services.slr.dedupe_service import ClassifiedDuplicateGroup, SLRDedupeService
from zotero_cli.core.services.slr.orchestrator import SLROrchestrator


@pytest.fixture
def gateway():
    return Mock(spec=ZoteroGateway)


@pytest.fixture
def duplicate_finder():
    finder = Mock(spec=DuplicateFinder)
    finder.warnings = []
    return finder


@pytest.fixture
def merge_service():
    return Mock(spec=MergeService)


@pytest.fixture
def sdb_service():
    return Mock(spec=SDBService)


@pytest.fixture
def orchestrator():
    return Mock(spec=SLROrchestrator)


@pytest.fixture
def service(gateway, duplicate_finder, merge_service, sdb_service, orchestrator):
    return SLRDedupeService(gateway, duplicate_finder, merge_service, sdb_service, orchestrator)


def make_group(match_type, identifier, occ_specs):
    return DuplicateGroup(
        match_type=match_type,
        identifier=identifier,
        occurrences=[
            DuplicateOccurrence(key=k, collection_id=c, title=t) for k, c, t in occ_specs
        ],
    )


def test_source_collection_ids_includes_raw_parents_and_phase_subfolders(service, gateway):
    gateway.get_all_collections.return_value = [
        {"key": "ROOT_A", "data": {"name": "raw_ieee", "parentCollection": None}},
        {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "ROOT_A"}},
        {"key": "C2", "data": {"name": "2-fulltext", "parentCollection": "ROOT_A"}},
        {"key": "ROOT_B", "data": {"name": "raw_acm", "parentCollection": None}},
        {"key": "OTHER", "data": {"name": "Unrelated", "parentCollection": None}},
    ]

    ids = service.source_collection_ids()

    assert set(ids) == {"ROOT_A", "C1", "C2", "ROOT_B"}


def test_find_and_classify_uses_source_tree_when_scope_omitted(
    service, gateway, duplicate_finder
):
    gateway.get_all_collections.return_value = [
        {"key": "ROOT_A", "data": {"name": "raw_ieee", "parentCollection": None}},
    ]
    duplicate_finder.compare_collections.return_value = []
    duplicate_finder.warnings = ["some warning"]

    result = service.find_and_classify()

    duplicate_finder.compare_collections.assert_called_once_with(["ROOT_A"])
    assert result == []
    assert service.warnings == ["some warning"]


def test_find_and_classify_uses_given_scope(service, duplicate_finder, gateway):
    duplicate_finder.compare_collections.return_value = []
    service.find_and_classify(["COL_X"])
    duplicate_finder.compare_collections.assert_called_once_with(["COL_X"])
    gateway.get_all_collections.assert_not_called()


def test_classify_matching(service, duplicate_finder, sdb_service):
    group = make_group("doi", "10.1/x", [("K1", "COL_A", "T1"), ("K2", "COL_B", "T2")])
    duplicate_finder.compare_collections.return_value = [group]
    sdb_service.inspect_item_sdb.return_value = [{"decision": "accepted"}]

    result = service.find_and_classify(["X"])

    assert len(result) == 1
    assert result[0].sdb_status == "MATCHING"
    assert {o.key for o in result[0].occurrences} == {"K1", "K2"}


def test_classify_conflicting(service, duplicate_finder, sdb_service):
    group = make_group("doi", "10.1/x", [("K1", "COL_A", "T1"), ("K2", "COL_B", "T2")])
    duplicate_finder.compare_collections.return_value = [group]

    def entries_for(key):
        return [{"decision": "accepted" if key == "K1" else "rejected"}]

    sdb_service.inspect_item_sdb.side_effect = entries_for

    result = service.find_and_classify(["X"])

    assert result[0].sdb_status == "CONFLICTING"


def test_classify_unscreened(service, duplicate_finder, sdb_service):
    group = make_group("doi", "10.1/x", [("K1", "COL_A", "T1"), ("K2", "COL_B", "T2")])
    duplicate_finder.compare_collections.return_value = [group]
    sdb_service.inspect_item_sdb.return_value = []

    result = service.find_and_classify(["X"])

    assert result[0].sdb_status == "UNSCREENED"


def test_build_reconciliation_plan_auto_fills_matching_and_unscreened(service):
    groups = [
        ClassifiedDuplicateGroup(
            match_type="doi",
            identifier="10.1/x",
            sdb_status="MATCHING",
            occurrences=[
                Mock(key="B", collection_id="C1", title="T"),
                Mock(key="A", collection_id="C2", title="T"),
            ],
        ),
        ClassifiedDuplicateGroup(
            match_type="title",
            identifier="paper y",
            sdb_status="UNSCREENED",
            occurrences=[
                Mock(key="D", collection_id="C1", title="T"),
                Mock(key="C", collection_id="C2", title="T"),
            ],
        ),
    ]

    plan = service.build_reconciliation_plan(groups)

    assert len(plan.entries) == 2
    matching_entry = plan.entries[0]
    assert matching_entry.decision is not None
    assert matching_entry.decision.master_key == "A"
    assert matching_entry.decision.merge_keys == ["B"]

    unscreened_entry = plan.entries[1]
    assert unscreened_entry.decision is not None
    assert unscreened_entry.decision.master_key == "C"
    assert unscreened_entry.decision.merge_keys == ["D"]


def test_build_reconciliation_plan_leaves_conflicting_undecided(service):
    groups = [
        ClassifiedDuplicateGroup(
            match_type="doi",
            identifier="10.1/x",
            sdb_status="CONFLICTING",
            occurrences=[
                Mock(key="A", collection_id="C1", title="T"),
                Mock(key="B", collection_id="C2", title="T"),
            ],
        ),
    ]

    plan = service.build_reconciliation_plan(groups)

    assert plan.entries[0].decision is None


def test_execute_reconciliation_dry_run_does_not_write_provenance(
    service, merge_service, orchestrator, sdb_service
):
    plan = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="doi:10.1/x",
                match_type="doi",
                identifier="10.1/x",
                occurrences=[DuplicateOccurrence(key="A", collection_id="C1")],
                decision=Mock(master_key="A", merge_keys=["B"], reason="test"),
            )
        ]
    )
    merge_service.execute_plan.return_value = PlanExecutionResult(success=True, dry_run=True)

    result = service.execute_reconciliation(plan, dry_run=True)

    assert result.dry_run is True
    orchestrator.record_duplicate_resolution.assert_not_called()
    sdb_service.inspect_item_sdb.assert_not_called()


def test_execute_reconciliation_writes_provenance_gathered_before_merge(
    service, merge_service, orchestrator, sdb_service
):
    decision = Mock(master_key="A", merge_keys=["B"], reason="SLR dedupe auto-resolution")
    plan = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="doi:10.1/x",
                match_type="doi",
                identifier="10.1/x",
                occurrences=[
                    DuplicateOccurrence(key="A", collection_id="C1"),
                    DuplicateOccurrence(key="B", collection_id="C2"),
                ],
                decision=decision,
            )
        ]
    )

    def entries_for(key):
        return [{"decision": "accepted"}] if key == "A" else [{"decision": "accepted"}]

    sdb_service.inspect_item_sdb.side_effect = entries_for
    merge_service.execute_plan.return_value = PlanExecutionResult(
        success=True,
        dry_run=False,
        group_results=[MergeResult(success=True, dry_run=False, master_key="A", merged_keys=["B"])],
    )

    result = service.execute_reconciliation(plan, dry_run=False)

    assert result.success is True
    orchestrator.record_duplicate_resolution.assert_called_once()
    call_kwargs = orchestrator.record_duplicate_resolution.call_args.kwargs
    assert call_kwargs["item_key"] == "A"
    assert call_kwargs["duplicate_key"] == "B"
    assert call_kwargs["provenance"] == [
        {"key": "A", "collection_id": "C1", "decisions": ["accepted"]},
        {"key": "B", "collection_id": "C2", "decisions": ["accepted"]},
    ]


def test_execute_reconciliation_skips_provenance_when_execute_plan_fails(
    service, merge_service, orchestrator, sdb_service
):
    decision = Mock(master_key="A", merge_keys=["B"], reason="test")
    plan = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="doi:10.1/x",
                match_type="doi",
                identifier="10.1/x",
                occurrences=[DuplicateOccurrence(key="A", collection_id="C1")],
                decision=decision,
            )
        ]
    )
    sdb_service.inspect_item_sdb.return_value = []
    merge_service.execute_plan.return_value = PlanExecutionResult(
        success=False, dry_run=False, errors=["boom"]
    )

    result = service.execute_reconciliation(plan, dry_run=False)

    assert result.success is False
    orchestrator.record_duplicate_resolution.assert_not_called()
