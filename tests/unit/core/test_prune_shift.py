from unittest.mock import Mock

import pytest

from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.services.slr.snapshot import SnapshotDiffService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_item_repo():
    return Mock()


@pytest.fixture
def mock_col_repo():
    return Mock()


@pytest.fixture
def col_service(mock_item_repo, mock_col_repo):
    return CollectionService(mock_item_repo, mock_col_repo)


def _item(key, collections, doi=None, parent=None):
    data = {"title": f"Paper {key}", "version": 3, "itemType": "journalArticle", "collections": collections}
    if doi:
        data["DOI"] = doi
    if parent:
        data["parentItem"] = parent
    return ZoteroItem.from_raw_zotero_item({"key": key, "data": data})


def _collections(mock_col_repo, contents):
    """contents: collection key -> items; names resolve to keys 'Inc'->'1', 'Exc'->'2'."""
    names = {"Inc": "1", "Exc": "2"}
    mock_col_repo.get_collection_id_by_name.side_effect = lambda x: names.get(x, x if x in contents else None)
    mock_col_repo.get_items_in_collection.side_effect = lambda key, **kw: iter(contents.get(key, []))


def test_prune_takes_the_same_item_and_duplicate_imports_out_of_excluded(
    col_service, mock_col_repo, mock_item_repo
):
    """Issue #395: duplicate imports (same DOI, different key) used to be
    permanently DELETED; now they're only removed from --excluded."""
    same = _item("A", ["1", "2"])
    dup_in_inc = _item("B1", ["1"], doi="10.1234/x")
    dup_in_exc = _item("B2", ["2", "9"], doi="10.1234/X")
    unrelated = _item("C", ["2"])
    _collections(mock_col_repo, {"1": [same, dup_in_inc], "2": [same, dup_in_exc, unrelated]})
    mock_item_repo.update_item.return_value = True

    plan = col_service.plan_prune("Inc", "Exc")
    assert [i.key for i in plan.items] == ["A", "B2"]

    removed, failed = col_service.remove_from_collection(plan)

    assert (removed, failed) == (2, [])
    mock_item_repo.delete_item.assert_not_called()
    mock_item_repo.update_item.assert_any_call("A", 3, {"collections": ["1"]})
    mock_item_repo.update_item.assert_any_call("B2", 3, {"collections": ["9"]})


def test_clean_plans_removal_without_deleting(col_service, mock_col_repo, mock_item_repo):
    """Issue #364: `collection clean` hard-deleted every item."""
    only_here = _item("A", ["2"])
    also_elsewhere = _item("B", ["2", "7"])
    _collections(mock_col_repo, {"2": [only_here, also_elsewhere]})
    mock_item_repo.update_item.side_effect = [True, False]

    plan = col_service.plan_clean("Exc")
    assert [i.key for i in plan.becomes_unfiled] == ["A"]
    removed, failed = col_service.remove_from_collection(plan)

    assert (removed, failed) == (1, ["B"])
    mock_item_repo.delete_item.assert_not_called()


def test_recursive_delete_keeps_items_filed_outside_the_tree(col_service, mock_col_repo, mock_item_repo):
    """Issue #378: items also filed in another collection were deleted with the tree."""
    mock_col_repo.get_all_collections.return_value = [
        {"key": "ROOT", "version": 5, "data": {"name": "Old project", "parentCollection": False}},
        {"key": "SUB", "version": 6, "data": {"name": "Sub", "parentCollection": "ROOT"}},
        {"key": "ELSEWHERE", "version": 1, "data": {"name": "Keep", "parentCollection": False}},
    ]
    only_in_tree = _item("A", ["ROOT", "SUB"])
    shared = _item("B", ["SUB", "ELSEWHERE"])
    child_note = _item("N", [], parent="A")
    _collections(mock_col_repo, {"ROOT": [only_in_tree, child_note], "SUB": [only_in_tree, shared]})
    mock_item_repo.delete_item.return_value = True
    mock_col_repo.delete_collection.return_value = True

    plan = col_service.plan_recursive_delete("ROOT")
    assert [k for k, _, _ in plan.collections] == ["SUB", "ROOT"]  # deepest first
    assert [i.key for i in plan.items_to_delete] == ["A"]
    assert [i.key for i in plan.shared_items] == ["B"]

    result = col_service.execute_recursive_delete(plan)
    mock_item_repo.delete_item.assert_called_once_with("A", 3)
    assert result.deleted_collections == 2

    mock_item_repo.delete_item.reset_mock()
    col_service.execute_recursive_delete(plan, include_shared=True)
    assert {c.args[0] for c in mock_item_repo.delete_item.call_args_list} == {"A", "B"}


def test_recursive_delete_leaves_collections_when_an_item_delete_fails(
    col_service, mock_col_repo, mock_item_repo
):
    mock_col_repo.get_all_collections.return_value = [
        {"key": "ROOT", "version": 5, "data": {"name": "R", "parentCollection": False}}
    ]
    _collections(mock_col_repo, {"ROOT": [_item("A", ["ROOT"])]})
    mock_item_repo.delete_item.return_value = False

    result = col_service.execute_recursive_delete(col_service.plan_recursive_delete("ROOT"))

    assert result.failed_items == ["A"]
    mock_col_repo.delete_collection.assert_not_called()


def test_analyze_shift():
    # Setup Snapshot Data
    snap_old = [
        {"key": "A", "title": "Paper A", "collections": ["Raw"]},
        {"key": "B", "title": "Paper B", "collections": ["Raw"]},
    ]
    snap_new = [
        {"key": "A", "title": "Paper A", "collections": ["Included"]},  # Moved
        {"key": "B", "title": "Paper B", "collections": ["Raw"]},  # Same
    ]

    diff_service = SnapshotDiffService()
    shifts = diff_service.detect_shifts(snap_old, snap_new)

    assert len(shifts) == 1
    assert shifts[0]["key"] == "A"
    assert shifts[0]["from"] == ["Raw"]
    assert shifts[0]["to"] == ["Included"]
