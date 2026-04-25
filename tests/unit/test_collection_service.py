from unittest.mock import MagicMock, Mock

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    mock = MagicMock(spec=ZoteroGateway)
    mock.get_item_children.return_value = []
    return mock


@pytest.fixture
def service(mock_gateway):
    return CollectionService(mock_gateway, mock_gateway)


def test_move_item_success_doi(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = (
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    )

    raw_item = {
        "key": "ITEM1",
        "data": {
            "key": "ITEM1",
            "version": 1,
            "DOI": "10.1234/test",
            "collections": ["ID_SRC", "ID_OTHER"]
        },
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    
    # First call None (trigger search), subsequent calls return item (re-fetch)
    mock_gateway.get_item.side_effect = [None, item, item, item]
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.update_items.return_value = True

    result = service.move_item("Source", "Dest", "10.1234/test")

    assert result is True
    assert mock_gateway.update_items.called
    args = mock_gateway.update_items.call_args[0][0]
    parent_update = next(p for p in args if p["key"] == "ITEM1")
    assert "ID_DEST" in parent_update["collections"]
    assert "ID_SRC" not in parent_update["collections"]


def test_move_item_not_found(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = (
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    )
    mock_gateway.get_item.return_value = None
    mock_gateway.get_items_in_collection.return_value = iter([])

    result = service.move_item("Source", "Dest", "missing")
    assert result is False
    mock_gateway.update_items.assert_not_called()


def test_move_item_success_arxiv(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = (
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    )

    raw_item = {
        "key": "ITEM2",
        "data": {
            "key": "ITEM2",
            "version": 5,
            "extra": "arXiv: 2301.00001",
            "collections": ["ID_SRC"]
        },
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    mock_gateway.get_item.side_effect = [None, item, item]
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.update_items.return_value = True

    result = service.move_item("Source", "Dest", "2301.00001")
    assert result is True


def test_move_item_success_key(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = (
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    )

    raw_item = {"key": "KEY123", "data": {"key": "KEY123", "version": 1, "collections": ["ID_SRC"]}}
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    mock_gateway.get_item.return_value = item
    mock_gateway.update_items.return_value = True

    result = service.move_item("Source", "Dest", "KEY123")

    assert result is True
    assert mock_gateway.update_items.called


def test_move_item_auto_source_success(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = (
        lambda name: "ID_DEST" if name == "Dest" else None
    )

    raw_item = {
        "key": "KEY1",
        "data": {
            "key": "KEY1",
            "version": 1,
            "collections": ["ID_SRC"],
        },
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    mock_gateway.get_item.return_value = item
    mock_gateway.update_items.return_value = True

    result = service.move_item(None, "Dest", "KEY1")

    assert result is True
    args = mock_gateway.update_items.call_args[0][0]
    parent_update = next(p for p in args if p["key"] == "KEY1")
    assert "ID_DEST" in parent_update["collections"]
    assert "ID_SRC" not in parent_update["collections"]

# (Rest of tests kept as is, they don't use update_items or re-fetch as much or are simpler)

def test_delete_collection_recursive(service, mock_gateway):
    raw1 = {"key": "K1", "data": {"key": "K1", "version": 1}}
    raw2 = {"key": "K2", "data": {"key": "K2", "version": 2}}
    item1 = ZoteroItem.from_raw_zotero_item(raw1)
    item2 = ZoteroItem.from_raw_zotero_item(raw2)

    mock_gateway.get_all_collections.return_value = []
    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])
    mock_gateway.delete_item.return_value = True
    mock_gateway.delete_collection.return_value = True

    result = service.delete_collection("COLL_ID", 1, recursive=True)

    assert result is True
    assert mock_gateway.delete_item.call_count == 2
    mock_gateway.delete_collection.assert_called_with("COLL_ID", 1)
