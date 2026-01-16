import pytest
from unittest.mock import Mock, MagicMock
from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_repo():
    return Mock()

@pytest.fixture
def mock_tag_repo():
    return Mock()

@pytest.fixture
def mock_note_repo():
    return Mock()

@pytest.fixture
def mock_collection_repo():
    return Mock()

@pytest.fixture
def mock_collection_service():
    return Mock()

@pytest.fixture
def service(mock_repo, mock_collection_repo, mock_note_repo, mock_tag_repo, mock_collection_service):
    # Signature: item_repo, collection_repo, note_repo, tag_repo, collection_service
    return ScreeningService(mock_repo, mock_collection_repo, mock_note_repo, mock_tag_repo, mock_collection_service)

def test_get_pending_items_skips_existing_tags(service, mock_collection_repo, mock_repo, mock_note_repo):
    # Setup: 2 Items
    # Item A: No tags
    item_fresh = ZoteroItem.from_raw_zotero_item({
        "key": "A", 
        "data": {"title": "Fresh Paper", "version": 1, "itemType": "journalArticle", "tags": []}
    })
    # Item B: Has "rsl:include" tag
    item_decided = ZoteroItem.from_raw_zotero_item({
        "key": "B", 
        "data": {
            "title": "Decided Paper", 
            "version": 1, 
            "itemType": "journalArticle", 
            "tags": [{"tag": "rsl:include"}, {"tag": "rsl:phase:title_abstract"}]
        }
    })
    
    # Mock Repository returning these items
    mock_collection_repo.get_collection_id_by_name.return_value = "col_123"
    mock_collection_repo.get_items_in_collection.return_value = iter([item_fresh, item_decided])
    
    # Mock Note Repository behavior
    # Item A (Fresh): Falls through to Slow Path -> returns no notes
    # Item B (Decided): Fast Path catches it -> Should NOT call get_item_children
    def get_children_side_effect(item_key):
        if item_key == "A":
            return [] # No notes
        if item_key == "B":
            # If called (it shouldn't be), return empty to prove logic relies on tags
            return []
        return []

    mock_note_repo.get_item_children.side_effect = get_children_side_effect

    # Action
    pending = list(service.get_pending_items("col_name"))

    # Assertion
    assert len(pending) == 1
    assert pending[0].key == "A"
    
    # Verify optimization: Called for A (Slow Path), NOT called for B (Fast Path)
    mock_note_repo.get_item_children.assert_called_with("A")
    # To verify B was skipped, we check call_args_list
    called_args = [call.args[0] for call in mock_note_repo.get_item_children.call_args_list]
    assert "B" not in called_args
