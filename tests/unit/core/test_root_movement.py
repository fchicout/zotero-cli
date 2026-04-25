from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_item_repo():
    return MagicMock()


@pytest.fixture
def mock_collection_repo():
    return MagicMock()


@pytest.fixture
def service(mock_item_repo, mock_collection_repo):
    return CollectionService(mock_item_repo, mock_collection_repo)


def test_move_to_root_keyword(service, mock_item_repo, mock_collection_repo):
    # Setup
    raw_item = {
        "key": "K1",
        "data": {
            "version": 1,
            "itemType": "journalArticle",
            "collections": ["COL1"]
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    mock_item_repo.get_item.return_value = item
    mock_collection_repo.get_collection_id_by_name.side_effect = (
        lambda x: None if x in ["/", "root", "unfiled"] else x
    )
    mock_item_repo.update_items.return_value = True
    mock_item_repo.get_item_children.return_value = []

    # Execute & Verify for each keyword
    for kw in ["/", "root", "unfiled", "ROOT", "Unfiled"]:
        success = service.move_item("COL1", kw, "K1")
        assert success is True
        # Check that update_items was called with payload containing collections=[]
        args = mock_item_repo.update_items.call_args[0][0]
        assert any(p["key"] == "K1" and p["collections"] == [] for p in args)


def test_move_from_root_keyword(service, mock_item_repo, mock_collection_repo):
    # Setup
    raw_item = {
        "key": "K1",
        "data": {
            "version": 1,
            "itemType": "journalArticle",
            "collections": []
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    mock_item_repo.get_item.return_value = item
    mock_collection_repo.get_collection_id_by_name.side_effect = (
        lambda x: None if x in ["/", "root", "unfiled"] else x
    )
    mock_item_repo.update_items.return_value = True
    mock_item_repo.get_item_children.return_value = []

    # Execute
    success = service.move_item("root", "COL2", "K1")

    # Verify
    assert success is True
    # Moving from root to COL2 means new collection list should be ["COL2"]
    args = mock_item_repo.update_items.call_args[0][0]
    assert any(p["key"] == "K1" and p["collections"] == ["COL2"] for p in args)


def test_auto_inference_from_root(service, mock_item_repo, mock_collection_repo):
    # Setup: Item is in zero collections (unfiled)
    raw_item = {
        "key": "K1",
        "data": {
            "version": 1,
            "itemType": "journalArticle",
            "collections": []
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    mock_item_repo.get_item.return_value = item
    mock_collection_repo.get_collection_id_by_name.return_value = "COL2"
    mock_item_repo.update_items.return_value = True
    mock_item_repo.get_item_children.return_value = []

    # Execute: Source is None
    success = service.move_item(None, "COL2", "K1")

    # Verify: Should infer move from root to COL2
    assert success is True
    args = mock_item_repo.update_items.call_args[0][0]
    assert any(p["key"] == "K1" and p["collections"] == ["COL2"] for p in args)
