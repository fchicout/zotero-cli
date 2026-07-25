from unittest.mock import Mock

import pytest

from zotero_cli.core.interfaces import ItemRepository, NoteRepository
from zotero_cli.core.services.duplicate_service import DuplicateGroup, DuplicateOccurrence
from zotero_cli.core.services.merge_service import MergeDecision, MergeService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def item_repo():
    return Mock(spec=ItemRepository)


@pytest.fixture
def note_repo():
    return Mock(spec=NoteRepository)


@pytest.fixture
def service(item_repo, note_repo):
    return MergeService(item_repo, note_repo)


def make_item(
    key,
    title="Title",
    doi=None,
    isbn=None,
    date=None,
    url=None,
    abstract=None,
    item_type="journalArticle",
    version=1,
    tags=None,
    collections=None,
):
    raw = {
        "key": key,
        "data": {
            "version": version,
            "itemType": item_type,
            "title": title,
            "DOI": doi,
            "ISBN": isbn,
            "date": date,
            "url": url,
            "abstractNote": abstract,
            "tags": [{"tag": t} for t in (tags or [])],
            "collections": collections or [],
        },
    }
    return ZoteroItem.from_raw_zotero_item(raw)


def test_detect_conflicts_none_when_fields_agree(service, item_repo):
    master = make_item("M1", title="Same Title", doi="10.1/X")
    dup = make_item("D1", title="Same Title", doi="10.1/X")
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]

    conflicts = service.detect_conflicts("M1", ["D1"])
    assert conflicts == []


def test_detect_conflicts_reports_differing_fields(service, item_repo):
    master = make_item("M1", title="Title A", date="2020")
    dup = make_item("D1", title="Title B", date="2021")
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]

    conflicts = service.detect_conflicts("M1", ["D1"])
    fields = {c.field_name for c in conflicts}
    assert fields == {"title", "date"}


def test_detect_conflicts_ignores_field_only_set_on_one_side(service, item_repo):
    master = make_item("M1", title="Title A", doi=None)
    dup = make_item("D1", title="Title A", doi="10.1/ONLY_DUP")
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]

    conflicts = service.detect_conflicts("M1", ["D1"])
    assert conflicts == []


def test_merge_fails_when_master_not_found(service, item_repo):
    item_repo.get_item.side_effect = lambda k: None if k == "MISSING" else make_item(k)

    result = service.merge("MISSING", ["D1"])
    assert result.success is False
    assert "Master item 'MISSING' not found." in result.errors[0]
    item_repo.update_item.assert_not_called()


def test_merge_fails_when_duplicate_not_found(service, item_repo):
    master = make_item("M1")
    item_repo.get_item.side_effect = lambda k: master if k == "M1" else None

    result = service.merge("M1", ["MISSING"])
    assert result.success is False
    assert "MISSING" in result.errors[0]
    item_repo.update_item.assert_not_called()


def test_merge_fails_on_item_type_mismatch(service, item_repo):
    master = make_item("M1", item_type="journalArticle")
    dup = make_item("D1", item_type="book")
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]

    result = service.merge("M1", ["D1"])
    assert result.success is False
    assert "Item type mismatch" in result.errors[0]
    item_repo.update_item.assert_not_called()


def test_merge_refuses_unresolved_conflicts(service, item_repo):
    master = make_item("M1", title="Title A")
    dup = make_item("D1", title="Title B")
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]

    result = service.merge("M1", ["D1"], dry_run=False)
    assert result.success is False
    assert len(result.unresolved_conflicts) == 1
    assert result.unresolved_conflicts[0].field_name == "title"
    item_repo.update_item.assert_not_called()
    item_repo.delete_item.assert_not_called()


def test_merge_dry_run_previews_without_writing(service, item_repo):
    master = make_item("M1", tags=["a"], collections=["C1"])
    dup = make_item("D1", tags=["b"], collections=["C2"])
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]
    item_repo.get_item_children.return_value = [
        {"key": "NOTE1", "data": {"itemType": "note", "version": 1, "note": "hello"}},
        {"key": "ATT1", "data": {"itemType": "attachment", "version": 1}},
    ]

    result = service.merge("M1", ["D1"], dry_run=True)

    assert result.success is True
    assert result.dry_run is True
    assert result.tags_added == 1
    assert result.collections_added == 1
    assert result.notes_moved == 1
    assert result.attachments_moved == 1
    item_repo.update_item.assert_not_called()
    item_repo.update_items.assert_not_called()
    item_repo.delete_item.assert_not_called()


def test_merge_executes_full_flow(service, item_repo, note_repo):
    master = make_item("M1", tags=["a"], collections=["C1"], version=1)
    dup = make_item("D1", tags=["b"], collections=["C2"], version=5)
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]
    item_repo.get_item_children.return_value = [
        {"key": "NOTE1", "data": {"itemType": "note", "version": 2, "note": "hello"}},
        {"key": "ATT1", "data": {"itemType": "attachment", "version": 3}},
    ]
    item_repo.update_item.return_value = True
    item_repo.update_items.return_value = True
    item_repo.delete_item.return_value = True
    note_repo.update_note.return_value = True

    result = service.merge("M1", ["D1"], dry_run=False)

    assert result.success is True
    assert result.merged_keys == ["D1"]
    assert result.notes_moved == 1
    assert result.attachments_moved == 1

    update_call = item_repo.update_item.call_args
    assert update_call[0][0] == "M1"
    assert update_call[0][1] == 1
    payload = update_call[0][2]
    assert {"tag": "a"} in payload["tags"] and {"tag": "b"} in payload["tags"]
    assert set(payload["collections"]) == {"C1", "C2"}

    note_repo.update_note.assert_called_once_with("NOTE1", 2, "hello", parent_item_key="M1")
    item_repo.update_items.assert_called_once_with(
        [{"key": "ATT1", "version": 3, "parentItem": "M1"}]
    )
    item_repo.delete_item.assert_called_once_with("D1", 5)


def test_merge_applies_field_resolutions(service, item_repo, note_repo):
    master = make_item("M1", title="Title A", version=1)
    dup = make_item("D1", title="Title B", version=1)
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]
    item_repo.get_item_children.return_value = []
    item_repo.update_item.return_value = True
    item_repo.delete_item.return_value = True

    result = service.merge(
        "M1", ["D1"], field_resolutions={"title": "Resolved Title"}, dry_run=False
    )

    assert result.success is True
    assert result.field_resolutions_applied == {"title": "Resolved Title"}
    update_call = item_repo.update_item.call_args
    assert update_call[0][2]["title"] == "Resolved Title"


def test_merge_records_error_when_master_update_fails(service, item_repo):
    master = make_item("M1", tags=["a"])
    dup = make_item("D1", tags=["b"])
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]
    item_repo.get_item_children.return_value = []
    item_repo.update_item.return_value = False

    result = service.merge("M1", ["D1"], dry_run=False)

    assert result.success is False
    assert "Failed to update master item 'M1'." in result.errors
    item_repo.delete_item.assert_not_called()


def test_merge_continues_and_reports_partial_failures(service, item_repo, note_repo):
    master = make_item("M1")
    dup = make_item("D1", version=5)
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]
    item_repo.get_item_children.return_value = []
    item_repo.update_item.return_value = True
    item_repo.delete_item.return_value = False

    result = service.merge("M1", ["D1"], dry_run=False)

    assert result.success is False
    assert "Failed to delete duplicate item 'D1' after merge." in result.errors
    assert result.merged_keys == []


# --- build_plan / execute_plan ---------------------------------------------


def make_group(match_type="doi", identifier="10.1/x", keys=("M1", "D1")):
    return DuplicateGroup(
        match_type=match_type,
        identifier=identifier,
        occurrences=[DuplicateOccurrence(key=k, collection_id="C1", title="T") for k in keys],
    )


def test_build_plan_produces_undecided_entries_with_deterministic_group_id():
    plan = MergeService.build_plan([make_group(match_type="doi", identifier="10.1/x")])
    assert len(plan.entries) == 1
    entry = plan.entries[0]
    assert entry.group_id == "doi:10.1/x"
    assert entry.decision is None
    assert [o.key for o in entry.occurrences] == ["M1", "D1"]


def test_execute_plan_refuses_all_writes_if_any_entry_undecided(service, item_repo):
    plan = MergeService.build_plan([make_group(), make_group(identifier="10.1/y", keys=("M2", "D2"))])
    plan.entries[0].decision = MergeDecision(master_key="M1", merge_keys=["D1"], reason="dup")
    # entries[1] left undecided

    result = service.execute_plan(plan, dry_run=False)

    assert result.success is False
    assert result.group_results == []
    assert any("has no decision" in e for e in result.errors)
    item_repo.update_item.assert_not_called()
    item_repo.delete_item.assert_not_called()


def test_execute_plan_rejects_decision_missing_reason(service):
    plan = MergeService.build_plan([make_group()])
    plan.entries[0].decision = MergeDecision(master_key="M1", merge_keys=["D1"], reason="")

    result = service.execute_plan(plan, dry_run=False)
    assert result.success is False
    assert any("no reason" in e for e in result.errors)


def test_execute_plan_rejects_incomplete_role_coverage(service):
    plan = MergeService.build_plan([make_group(keys=("M1", "D1", "D2"))])
    # D2 has no role at all
    plan.entries[0].decision = MergeDecision(master_key="M1", merge_keys=["D1"], reason="dup")

    result = service.execute_plan(plan, dry_run=False)
    assert result.success is False
    assert any("D2" in e and "no role" in e for e in result.errors)


def test_execute_plan_rejects_master_key_not_in_group():
    plan = MergeService.build_plan([make_group()])
    plan.entries[0].decision = MergeDecision(master_key="NOT_IN_GROUP", merge_keys=["D1"], reason="x")

    result = MergeService(Mock(spec=ItemRepository), Mock(spec=NoteRepository)).execute_plan(
        plan, dry_run=False
    )
    assert result.success is False
    assert any("not one of this group" in e for e in result.errors)


def test_execute_plan_skips_group_with_no_merge_keys(service, item_repo):
    plan = MergeService.build_plan([make_group(keys=("M1", "D1"))])
    plan.entries[0].decision = MergeDecision(master_key="M1", keep_keys=["D1"], reason="not a dup")

    result = service.execute_plan(plan, dry_run=False)

    assert result.success is True
    assert result.group_results == []
    item_repo.get_item.assert_not_called()


def test_execute_plan_dry_run_previews_without_writing(service, item_repo):
    master = make_item("M1", tags=["a"])
    item_repo.get_item.side_effect = lambda k: {"M1": master}.get(k, make_item(k))
    item_repo.get_item_children.return_value = []

    plan = MergeService.build_plan([make_group()])
    plan.entries[0].decision = MergeDecision(master_key="M1", merge_keys=["D1"], reason="dup")

    result = service.execute_plan(plan, dry_run=True)

    assert result.success is True
    assert result.dry_run is True
    assert len(result.group_results) == 1
    assert result.group_results[0].dry_run is True
    item_repo.update_item.assert_not_called()
    item_repo.delete_item.assert_not_called()


def test_execute_plan_executes_and_auto_resolves_conflicts_to_master_value(
    service, item_repo, note_repo
):
    master = make_item("M1", title="Master Title", version=1)
    dup = make_item("D1", title="Duplicate Title", version=3)
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]
    item_repo.get_item_children.return_value = []
    item_repo.update_item.return_value = True
    item_repo.delete_item.return_value = True

    plan = MergeService.build_plan([make_group()])
    plan.entries[0].decision = MergeDecision(master_key="M1", merge_keys=["D1"], reason="dup")

    result = service.execute_plan(plan, dry_run=False)

    assert result.success is True
    assert len(result.group_results) == 1
    assert result.group_results[0].success is True
    # Master's own title was used to auto-resolve the title conflict - no
    # interactive prompt possible in a batch execution path.
    update_payload = item_repo.update_item.call_args[0][2]
    assert update_payload["title"] == "Master Title"
    item_repo.delete_item.assert_called_once_with("D1", 3)


def test_execute_plan_reports_partial_group_failure(service, item_repo):
    master = make_item("M1")
    dup = make_item("D1")
    item_repo.get_item.side_effect = lambda k: {"M1": master, "D1": dup}[k]
    item_repo.get_item_children.return_value = []
    item_repo.update_item.return_value = False

    plan = MergeService.build_plan([make_group()])
    plan.entries[0].decision = MergeDecision(master_key="M1", merge_keys=["D1"], reason="dup")

    result = service.execute_plan(plan, dry_run=False)

    assert result.success is False
    assert len(result.group_results) == 1
    assert result.group_results[0].success is False
