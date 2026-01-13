import pytest
from unittest.mock import Mock
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)

@pytest.fixture
def service(mock_gateway):
    return CollectionService(mock_gateway)

def test_move_item_success_doi(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    
    raw_item = {
        'key': 'ITEM1',
        'data': {
            'version': 1,
            'DOI': '10.1234/test',
            'collections': ['ID_SRC', 'ID_OTHER']
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    # The new logic tries get_item first. Let's make it fail lookup by ID so it falls back to scan,
    # OR better, make it succeed if we pass the key, but here we pass DOI.
    # If we pass DOI "10.1234/test" to get_item, it should return None (not found by key).
    mock_gateway.get_item.return_value = None 
    
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.update_item_collections.return_value = True

    result = service.move_item("Source", "Dest", "10.1234/test")
    
    assert result is True
    args = mock_gateway.update_item_collections.call_args
    assert args[0][0] == 'ITEM1'
    assert args[0][1] == 1
    assert 'ID_DEST' in args[0][2]
    assert 'ID_SRC' not in args[0][2]
    assert 'ID_OTHER' in args[0][2]

def test_move_item_not_found(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    mock_gateway.get_item.return_value = None
    mock_gateway.get_items_in_collection.return_value = iter([])
    
    result = service.move_item("Source", "Dest", "missing")
    assert result is False
    mock_gateway.update_item_collections.assert_not_called()

def test_move_item_success_arxiv(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    
    raw_item = {
        'key': 'ITEM2',
        'data': {
            'version': 5,
            'extra': 'Some note\narXiv: 2301.00001',
            'collections': ['ID_SRC']
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    mock_gateway.get_item.return_value = None # Assume lookup by key fails for arxiv ID
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.update_item_collections.return_value = True

    result = service.move_item("Source", "Dest", "2301.00001")
    assert result is True
        
def test_collections_not_found(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    mock_gateway.get_item.return_value = None # Item not found by key
    mock_gateway.get_items_in_collection.return_value = iter([]) # Not found by scan either
    
    assert service.move_item("BadSource", "Dest", "id") is False
    assert service.move_item("Source", "BadDest", "id") is False

# New Test: Direct Key Lookup Success (The optimization)
def test_move_item_success_key(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)
    
    raw_item = {
        'key': 'KEY123',
        'data': {
            'version': 1,
            'collections': ['ID_SRC']
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    # This time get_item succeeds!
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_collections.return_value = True

    result = service.move_item("Source", "Dest", "KEY123")
    
    assert result is True
    mock_gateway.get_items_in_collection.assert_not_called() # Optimization verified!
    mock_gateway.update_item_collections.assert_called()

def test_empty_collection_success_simple(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "COLL_ID"
    
    item1 = Mock(spec=ZoteroItem); item1.key = "K1"; item1.version = 1
    item2 = Mock(spec=ZoteroItem); item2.key = "K2"; item2.version = 2
    
    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])
    mock_gateway.delete_item.return_value = True

    count = service.empty_collection("TargetCol")

    assert count == 2
    mock_gateway.get_collection_id_by_name.assert_called_with("TargetCol")
    mock_gateway.get_items_in_collection.assert_called_with("COLL_ID")
    assert mock_gateway.delete_item.call_count == 2

def test_empty_collection_with_parent_success(service, mock_gateway):
    mock_gateway.get_all_collections.return_value = [
        {'key': 'PARENT_ID', 'data': {'name': 'ParentCol'}},
        {'key': 'WRONG_CHILD', 'data': {'name': 'ChildCol', 'parentCollection': 'OTHER_ID'}},
        {'key': 'TARGET_ID', 'data': {'name': 'ChildCol', 'parentCollection': 'PARENT_ID'}}
    ]
    
    item1 = Mock(spec=ZoteroItem); item1.key = "K1"; item1.version = 1
    mock_gateway.get_items_in_collection.return_value = iter([item1])
    mock_gateway.delete_item.return_value = True

    count = service.empty_collection("ChildCol", parent_collection_name="ParentCol")

    assert count == 1
    mock_gateway.get_items_in_collection.assert_called_with("TARGET_ID")
    mock_gateway.delete_item.assert_called_once()

def test_empty_collection_parent_not_found(service, mock_gateway):
    mock_gateway.get_all_collections.return_value = []
    count = service.empty_collection("Child", parent_collection_name="MissingParent")
    assert count == 0
    mock_gateway.delete_item.assert_not_called()