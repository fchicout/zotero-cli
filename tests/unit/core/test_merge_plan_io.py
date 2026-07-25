from zotero_cli.core.services.duplicate_service import DuplicateGroup, DuplicateOccurrence
from zotero_cli.core.services.merge_plan_io import (
    parse_plan_from_csv,
    parse_plan_from_json,
    serialize_plan_to_csv,
    serialize_plan_to_json,
)
from zotero_cli.core.services.merge_service import MergeDecision, MergePlanEntry, MergeService


def make_plan_with_decision():
    group = DuplicateGroup(
        match_type="doi",
        identifier="10.1/x",
        occurrences=[
            DuplicateOccurrence(key="M1", collection_id="C1", title="Master Paper"),
            DuplicateOccurrence(key="D1", collection_id="C2", title="Dup Paper"),
        ],
    )
    plan = MergeService.build_plan([group])
    plan.entries[0].decision = MergeDecision(master_key="M1", merge_keys=["D1"], reason="Same DOI")
    return plan


def test_csv_round_trip_preserves_decision():
    plan = make_plan_with_decision()
    csv_text = serialize_plan_to_csv(plan)

    assert "MASTER" in csv_text and "MERGE" in csv_text and "Same DOI" in csv_text

    parsed = parse_plan_from_csv(csv_text)
    assert len(parsed.entries) == 1
    entry = parsed.entries[0]
    assert entry.group_id == "doi:10.1/x"
    assert {o.key for o in entry.occurrences} == {"M1", "D1"}
    assert entry.decision is not None
    assert entry.decision.master_key == "M1"
    assert entry.decision.merge_keys == ["D1"]
    assert entry.decision.reason == "Same DOI"


def test_csv_round_trip_undecided_group_stays_undecided():
    group = DuplicateGroup(
        match_type="title",
        identifier="common title",
        occurrences=[
            DuplicateOccurrence(key="A1", collection_id="C1", title="Common Title"),
            DuplicateOccurrence(key="A2", collection_id="C2", title="Common Title"),
        ],
    )
    plan = MergeService.build_plan([group])

    csv_text = serialize_plan_to_csv(plan)
    parsed = parse_plan_from_csv(csv_text)

    assert len(parsed.entries) == 1
    assert parsed.entries[0].decision is None


def test_csv_parse_with_incomplete_role_coverage_is_caught_by_execute_plan_validation():
    # Hand-crafted CSV: only one row has a role, the other (D1) is blank.
    # parse_plan_from_csv is structural-only and won't fabricate coverage for
    # D1 - it's execute_plan's completeness validation that must catch this.
    csv_text = (
        "group_id,match_type,identifier,key,collection_id,title,role,reason\n"
        "doi:10.1/x,doi,10.1/x,M1,C1,Master Paper,MASTER,Same DOI\n"
        "doi:10.1/x,doi,10.1/x,D1,C2,Dup Paper,,\n"
    )
    parsed = parse_plan_from_csv(csv_text)
    assert parsed.entries[0].decision is not None
    assert parsed.entries[0].decision.merge_keys == []

    from unittest.mock import Mock

    from zotero_cli.core.interfaces import ItemRepository, NoteRepository

    service = MergeService(Mock(spec=ItemRepository), Mock(spec=NoteRepository))
    result = service.execute_plan(parsed, dry_run=True)
    assert result.success is False
    assert any("D1" in e and "no role" in e for e in result.errors)


def test_json_round_trip_preserves_decision_and_includes_sdb_history():
    plan = make_plan_with_decision()
    sdb_history = {"M1": [{"decision": "INCLUDE", "persona": "reviewer-a"}], "D1": []}

    json_text = serialize_plan_to_json(plan, sdb_history=sdb_history)
    assert "reviewer-a" in json_text

    parsed = parse_plan_from_json(json_text)
    assert len(parsed.entries) == 1
    entry = parsed.entries[0]
    assert entry.decision is not None
    assert entry.decision.master_key == "M1"
    assert entry.decision.merge_keys == ["D1"]
    assert entry.decision.reason == "Same DOI"
    assert {o.key for o in entry.occurrences} == {"M1", "D1"}


def test_json_round_trip_undecided_group():
    plan = MergePlanEntry(
        group_id="doi:10.1/y",
        match_type="doi",
        identifier="10.1/y",
        occurrences=[DuplicateOccurrence(key="X1", collection_id="C1", title="T")],
    )
    from zotero_cli.core.services.merge_service import MergePlan

    wrapped = MergePlan(entries=[plan])
    json_text = serialize_plan_to_json(wrapped)
    parsed = parse_plan_from_json(json_text)
    assert parsed.entries[0].decision is None


def test_json_serialization_includes_schema_version():
    plan = make_plan_with_decision()
    json_text = serialize_plan_to_json(plan)
    assert '"version": "1.0"' in json_text
