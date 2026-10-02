"""Failure paths of the destructive operations (Issue #389).

The invariant under test is the same everywhere: when a step fails, nothing
that was not already handled is deleted, orphaned or lost. Repositories are
`create_autospec` mocks, so a renamed or re-signed method fails the test
instead of being accepted by a bare MagicMock.
"""

from unittest.mock import create_autospec

import pytest

from zotero_cli.core.interfaces import CollectionRepository, ItemRepository, ZoteroGateway
from zotero_cli.core.services.collection_service import CollectionService, RecursiveDeletePlan
from zotero_cli.core.services.transfer_service import TransferService
from zotero_cli.core.zotero_item import ZoteroItem


def make_item(key, collections=(), parent=None, version=1, item_type="journalArticle"):
    data = {"itemType": item_type, "title": f"title {key}", "version": version}
    data["collections"] = list(collections)
    if parent:
        data["parentItem"] = parent
    return ZoteroItem.from_raw_zotero_item({"key": key, "version": version, "data": data})


@pytest.fixture
def item_repo():
    return create_autospec(ItemRepository, instance=True)


@pytest.fixture
def collection_repo():
    return create_autospec(CollectionRepository, instance=True)


@pytest.fixture
def service(item_repo, collection_repo):
    return CollectionService(item_repo, collection_repo)


# ---- sticky move: children keep their parent and share its collections -------------------


def test_a_move_keeps_every_child_attached_to_its_parent(service, item_repo):
    parent = make_item("P1", collections=["SRC"])
    child = make_item("C1", collections=["SRC"], parent="P1", item_type="note")
    item_repo.get_item_children.return_value = [child.raw_data]
    item_repo.get_item.side_effect = lambda key: {"P1": parent, "C1": child}[key]
    item_repo.update_items.return_value = True

    assert service._perform_move(parent, "SRC", "DEST") is True

    payload = {entry["key"]: entry for entry in item_repo.update_items.call_args.args[0]}
    assert payload["P1"]["collections"] == ["DEST"]
    assert payload["C1"]["collections"] == ["DEST"]
    assert payload["C1"]["parentItem"] == "P1"
    assert "parentItem" not in payload["P1"]


def test_a_failed_bulk_update_is_reported_as_a_failed_move(service, item_repo):
    parent = make_item("P1", collections=["SRC"])
    item_repo.get_item_children.return_value = []
    item_repo.get_item.return_value = parent
    item_repo.update_items.return_value = False

    assert service._perform_move(parent, "SRC", "DEST") is False


def test_a_move_with_nothing_to_change_sends_no_request(service, item_repo):
    parent = make_item("P1", collections=["DEST"])
    item_repo.get_item_children.return_value = []
    item_repo.get_item.return_value = parent

    assert service._perform_move(parent, "SRC", "DEST") is True
    item_repo.update_items.assert_not_called()


def test_a_child_that_vanished_is_skipped_not_fatal(service, item_repo):
    parent = make_item("P1", collections=["SRC"])
    gone = make_item("GONE", collections=["SRC"], parent="P1", item_type="note")
    item_repo.get_item_children.return_value = [gone.raw_data]
    item_repo.get_item.side_effect = lambda key: parent if key == "P1" else None
    item_repo.update_items.return_value = True

    assert service._perform_move(parent, "SRC", "DEST") is True
    sent = item_repo.update_items.call_args.args[0]
    assert [entry["key"] for entry in sent] == ["P1"]


# ---- resolving and creating collections ------------------------------------------------------


def test_get_or_create_finds_a_collection_by_name(service, collection_repo):
    collection_repo.get_collection_id_by_name.return_value = "KEY1"
    assert service.get_or_create_collection_id("Reviews") == "KEY1"
    collection_repo.create_collection.assert_not_called()


def test_get_or_create_accepts_a_collection_key(service, collection_repo):
    collection_repo.get_collection_id_by_name.return_value = None
    collection_repo.get_collection.return_value = {"key": "ABCD1234"}
    assert service.get_or_create_collection_id("ABCD1234") == "ABCD1234"
    collection_repo.create_collection.assert_not_called()


def test_get_or_create_creates_what_does_not_exist(service, collection_repo):
    collection_repo.get_collection_id_by_name.return_value = None
    collection_repo.get_collection.return_value = None
    collection_repo.create_collection.return_value = "NEW1"
    assert service.get_or_create_collection_id("Fresh") == "NEW1"


def test_get_or_create_refuses_to_continue_without_a_collection(service, collection_repo):
    collection_repo.get_collection_id_by_name.return_value = None
    collection_repo.get_collection.return_value = None
    collection_repo.create_collection.return_value = None
    with pytest.raises(ValueError, match="could not be created"):
        service.get_or_create_collection_id("Nope")


def test_resolve_collection_accepts_a_key_and_returns_none_for_unknown(service, collection_repo):
    collection_repo.get_collection_id_by_name.return_value = None
    collection_repo.get_collection.return_value = {"key": "ABCD1234"}
    assert service.resolve_collection("ABCD1234") == "ABCD1234"
    collection_repo.get_collection.return_value = None
    assert service.resolve_collection("nothing") is None


def test_clean_and_prune_plans_need_collections_that_exist(service, collection_repo):
    collection_repo.get_collection_id_by_name.return_value = None
    collection_repo.get_collection.return_value = None
    assert service.plan_clean("Missing") is None
    assert service.plan_prune("Missing", "AlsoMissing") is None


# ---- deleting collections ----------------------------------------------------------------------


def test_a_failed_collection_delete_is_listed_and_the_rest_still_run(
    service, item_repo, collection_repo
):
    plan = RecursiveDeletePlan(
        root_key="ROOT",
        collections=[("CHILD", 2, "Child"), ("ROOT", 1, "Root")],
        items_to_delete=[make_item("I1", collections=["ROOT"])],
    )
    item_repo.delete_item.return_value = True
    collection_repo.delete_collection.side_effect = [False, True]

    result = service.execute_recursive_delete(plan)

    assert result.deleted_items == 1
    assert result.failed_collections == ["CHILD"]
    assert result.deleted_collections == 1


def test_collections_survive_when_an_item_cannot_be_deleted(service, item_repo, collection_repo):
    plan = RecursiveDeletePlan(
        root_key="ROOT",
        collections=[("ROOT", 1, "Root")],
        items_to_delete=[make_item("I1", collections=["ROOT"])],
    )
    item_repo.delete_item.return_value = False

    result = service.execute_recursive_delete(plan)

    assert result.failed_items == ["I1"]
    collection_repo.delete_collection.assert_not_called()


def test_a_plain_delete_removes_only_the_collection_at_the_given_version(
    service, item_repo, collection_repo
):
    collection_repo.delete_collection.return_value = True

    assert service.delete_collection("COL1", 42) is True

    collection_repo.delete_collection.assert_called_once_with("COL1", 42)
    item_repo.delete_item.assert_not_called()
    item_repo.trash_item.assert_not_called()


# ---- transferring between libraries ------------------------------------------------------------


def test_nothing_is_deleted_when_the_destination_item_cannot_be_created():
    source = create_autospec(ZoteroGateway, instance=True)
    dest = create_autospec(ZoteroGateway, instance=True)
    source.get_item.return_value = make_item("S1", version=7)
    dest.create_generic_item.return_value = None

    result = TransferService().transfer_item("S1", source, dest, delete_source=True)

    assert result.new_key is None
    assert result.source_deleted is False
    assert result.failures == ["could not create the destination item"]
    source.delete_item.assert_not_called()
    source.trash_item.assert_not_called()


def test_a_recursive_delete_reports_failure_when_a_collection_could_not_go(
    service, item_repo, collection_repo
):
    collection_repo.get_collection.return_value = {
        "key": "ROOT",
        "version": 3,
        "data": {"name": "R"},
    }
    collection_repo.get_all_collections.return_value = [
        {"key": "ROOT", "version": 3, "data": {"name": "R", "parentCollection": False}}
    ]
    collection_repo.get_items_in_collection.return_value = iter([])
    collection_repo.delete_collection.return_value = False

    assert service.delete_collection("ROOT", 3, recursive=True) is False
