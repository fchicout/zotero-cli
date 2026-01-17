import json
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.snapshot_service import SnapshotService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def snapshot_service(mock_gateway):
    return SnapshotService(mock_gateway)


def test_freeze_collection_success(snapshot_service, mock_gateway, tmp_path):
    # Setup
    collection_name = "Test Collection"
    collection_id = "COLL123"
    output_file = tmp_path / "snapshot.json"

    mock_gateway.get_collection_id_by_name.return_value = collection_id

    # Mock Items
    item1 = ZoteroItem(
        key="ITEM1",
        version=1,
        item_type="journalArticle",
        title="Paper 1",
        abstract="Abstract 1",
        authors=["Author A"],
    )
    item2 = ZoteroItem(
        key="ITEM2",
        version=1,
        item_type="journalArticle",
        title="Paper 2",
        abstract="Abstract 2",
        authors=["Author B"],
    )
    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])

    # Mock Children
    mock_gateway.get_item_children.side_effect = [
        [
            {"key": "NOTE1", "itemType": "note", "note": "<div>Decision: INCLUDE</div>"}
        ],  # Children for ITEM1
        [],  # Children for ITEM2
    ]

    # Execute
    callback = MagicMock()
    success = snapshot_service.freeze_collection(collection_name, str(output_file), callback)

    # Verify
    assert success is True
    mock_gateway.get_collection_id_by_name.assert_called_with(collection_name)
    mock_gateway.get_items_in_collection.assert_called_with(collection_id)
    assert mock_gateway.get_item_children.call_count == 2

    # Check Callback
    # 1 (Resolve) + 1 (Fetch Items) + 2 (Items) + 1 (Write) = 5 calls
    assert callback.call_count >= 5

    # Verify Output File
    with open(output_file, "r") as f:
        data = json.load(f)

    assert data["meta"]["collection_name"] == collection_name
    assert data["meta"]["total_items_found"] == 2
    assert len(data["items"]) == 2

    item1_data = next(i for i in data["items"] if i["key"] == "ITEM1")
    assert item1_data["title"] == "Paper 1"
    assert len(item1_data["children"]) == 1
    assert item1_data["children"][0]["key"] == "NOTE1"


def test_freeze_collection_partial_failure(snapshot_service, mock_gateway, tmp_path):
    # Setup
    collection_name = "Partial Fail Collection"
    collection_id = "COLL_PARTIAL"
    output_file = tmp_path / "snapshot_partial.json"

    mock_gateway.get_collection_id_by_name.return_value = collection_id

    item1 = ZoteroItem(key="ITEM1", version=1, item_type="journalArticle", title="Paper 1")
    item2 = ZoteroItem(key="ITEM2", version=1, item_type="journalArticle", title="Paper 2")

    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])

    # Simulate first item succeeds, second item raises Exception
    mock_gateway.get_item_children.side_effect = [
        [],  # ITEM1 children
        Exception("API Rate Limit"),  # ITEM2 fails
    ]

    # Execute
    success = snapshot_service.freeze_collection(collection_name, str(output_file))

    # Verify
    assert success is True  # Should still return True (Partial Success)

    with open(output_file, "r") as f:
        data = json.load(f)

    assert data["meta"]["items_processed_successfully"] == 1
    assert data["meta"]["items_failed"] == 1
    assert data["meta"]["status"] == "partial_success"

    assert len(data["items"]) == 1
    assert data["items"][0]["key"] == "ITEM1"

    assert len(data["failures"]) == 1
    assert data["failures"][0]["key"] == "ITEM2"
    assert "API Rate Limit" in data["failures"][0]["error"]


def test_freeze_collection_not_found(snapshot_service, mock_gateway, tmp_path):
    collection_name = "Nonexistent"
    output_file = tmp_path / "snapshot.json"

    mock_gateway.get_collection_id_by_name.return_value = None

    success = snapshot_service.freeze_collection(collection_name, str(output_file))

    assert success is False
    assert not output_file.exists()


def test_freeze_collection_write_error(snapshot_service, mock_gateway, tmp_path):
    collection_name = "Test Collection"
    collection_id = "COLL123"
    # Invalid path (directory instead of file)
    output_file = tmp_path

    mock_gateway.get_collection_id_by_name.return_value = collection_id
    mock_gateway.get_items_in_collection.return_value = iter([])

    success = snapshot_service.freeze_collection(collection_name, str(output_file))

    assert success is False
