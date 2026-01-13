import pytest
from unittest.mock import MagicMock, patch
import json
from datetime import datetime, timezone

from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def screening_service(mock_gateway):
    return ScreeningService(mock_gateway)

def test_record_decision_success(screening_service, mock_gateway):
    item_key = "ITEM123"
    mock_gateway.create_note.return_value = True
    
    success = screening_service.record_decision(
        item_key=item_key,
        decision="INCLUDE",
        code="IC1",
        reason="Relevant study"
    )
    
    assert success is True
    # Verify note creation
    args, _ = mock_gateway.create_note.call_args
    assert args[0] == item_key
    note_content = args[1]
    assert "screening_decision" in note_content
    assert "accepted" in note_content
    assert "IC1" in note_content
    assert "Relevant study" in note_content
    assert "audit_version" in note_content
    assert "1.1" in note_content

def test_record_decision_with_move(screening_service, mock_gateway):
    item_key = "ITEM123"
    source_col = "Raw"
    target_col = "Screened"
    
    mock_gateway.create_note.return_value = True
    mock_gateway.get_collection_id_by_name.side_effect = ["SRC_ID", "TGT_ID"]
    
    item = ZoteroItem(key=item_key, version=10, item_type="journalArticle", collections=["SRC_ID", "OTHER_ID"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_collections.return_value = True
    
    success = screening_service.record_decision(
        item_key=item_key,
        decision="EXCLUDE",
        code="EC1",
        source_collection=source_col,
        target_collection=target_col
    )
    
    assert success is True
    # Verify move
    mock_gateway.update_item_collections.assert_called_once()
    # collections should have SRC_ID removed and TGT_ID added
    updated_cols = mock_gateway.update_item_collections.call_args[0][2]
    assert "SRC_ID" not in updated_cols
    assert "TGT_ID" in updated_cols
    assert "OTHER_ID" in updated_cols

def test_get_pending_items(screening_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "COL_ID"
    
    item1 = ZoteroItem(key="I1", version=1, item_type="journalArticle")
    item2 = ZoteroItem(key="I2", version=1, item_type="journalArticle")
    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])
    
    # item1 has decision note, item2 does not
    mock_gateway.get_item_children.side_effect = [
        [{"itemType": "note", "note": "screening_decision JSON ..."}],
        []
    ]
    
    pending = screening_service.get_pending_items("Any")
    
    assert len(pending) == 1
    assert pending[0].key == "I2"
