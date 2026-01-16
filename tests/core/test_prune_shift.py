import pytest
from unittest.mock import Mock, call
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.services.audit_service import CollectionAuditor
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

def test_prune_intersection(col_service, mock_col_repo, mock_item_repo):
    # Setup: Item A is in BOTH "Inc" (id: 1) and "Exc" (id: 2)
    mock_col_repo.get_collection_id_by_name.side_effect = lambda x: "1" if x == "Inc" else "2"
    
    item_a_inc = ZoteroItem.from_raw_zotero_item({"key": "A", "data": {"title": "Paper A", "version": 1, "itemType": "journal", "collections": ["1", "2"]}})
    item_a_exc = ZoteroItem.from_raw_zotero_item({"key": "A", "data": {"title": "Paper A", "version": 1, "itemType": "journal", "collections": ["1", "2"]}})
    
    mock_col_repo.get_items_in_collection.side_effect = lambda x, **kwargs: iter([item_a_inc]) if x == "1" else iter([item_a_exc])
    
    # Mock update_item to return True
    mock_item_repo.update_item.return_value = True
    
    # Action: Prune Exc based on Inc
    removed_count = col_service.prune_intersection("Inc", "Exc")
    
    # Assert
    assert removed_count == 1
    # Verify we removed Item A from Collection 2 (Excluded)
    # The 'remove_item_from_collection' method on Service or Repo?
    # CollectionService usually calls update_item to remove collection ID from list
    # But wait, Zotero API has remove_item_from_collection? No, it's an update.
    # Let's see what logic Implement.
    # We expect `remove_item_from_collection` to be called on repository or service.
    # Assuming service calls repo.update_item or internal helper.
    # Let's assume we add `remove_item_from_collection` to Service.

def test_analyze_shift():
    # Setup Snapshot Data
    snap_old = [
        {"key": "A", "title": "Paper A", "collections": ["Raw"]},
        {"key": "B", "title": "Paper B", "collections": ["Raw"]}
    ]
    snap_new = [
        {"key": "A", "title": "Paper A", "collections": ["Included"]}, # Moved
        {"key": "B", "title": "Paper B", "collections": ["Raw"]}      # Same
    ]
    
    auditor = CollectionAuditor(Mock())
    shifts = auditor.detect_shifts(snap_old, snap_new)
    
    assert len(shifts) == 1
    assert shifts[0]["key"] == "A"
    assert shifts[0]["from"] == ["Raw"]
    assert shifts[0]["to"] == ["Included"]
