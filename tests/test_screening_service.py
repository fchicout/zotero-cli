from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def screening_service(mock_gateway):
    # Pass mock_gateway for all repo interfaces since it implements them all
    # For collection_service, we use a mock
    mock_col_service = MagicMock()
    return ScreeningService(mock_gateway, mock_gateway, mock_gateway, mock_col_service)

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

    # Mock the internal collection service
    screening_service.collection_service.move_item.return_value = True

    success = screening_service.record_decision(
        item_key=item_key,
        decision="EXCLUDE",
        code="EC1",
        source_collection=source_col,
        target_collection=target_col
    )

    assert success is True
    # Verify move delegated to collection service
    screening_service.collection_service.move_item.assert_called_once_with(source_col, target_col, item_key)

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
