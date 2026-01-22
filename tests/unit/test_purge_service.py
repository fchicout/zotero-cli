import pytest
from unittest.mock import MagicMock
from zotero_cli.core.services.purge_service import PurgeService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def purge_service(mock_gateway):
    return PurgeService(mock_gateway)

def test_purge_attachments_dry_run(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 1}},
        {"key": "N1", "data": {"itemType": "note", "version": 1}}
    ]
    
    stats = purge_service.purge_attachments(["P1"], dry_run=True)
    
    assert stats["skipped"] == 1
    assert stats["deleted"] == 0
    mock_gateway.delete_item.assert_not_called()

def test_purge_attachments_execute(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 5}}
    ]
    mock_gateway.delete_item.return_value = True
    
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    
    assert stats["deleted"] == 1
    mock_gateway.delete_item.assert_called_once_with("A1", 5)

def test_purge_notes_sdb_filter(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "note": "Regular note", "version": 1}},
        {"key": "N2", "data": {"itemType": "note", "note": '{"audit_version": "1.2", "phase": "p1"}', "version": 1}}
    ]
    mock_gateway.delete_item.return_value = True
    
    # Only SDB
    stats = purge_service.purge_notes(["P1"], sdb_only=True, dry_run=False)
    assert stats["deleted"] == 1
    mock_gateway.delete_item.assert_called_once_with("N2", 1)

def test_purge_notes_phase_filter(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "note": '{"audit_version": "1.2", "phase": "title"}', "version": 1}},
        {"key": "N2", "data": {"itemType": "note", "note": '{"audit_version": "1.2", "phase": "fulltext"}', "version": 1}}
    ]
    mock_gateway.delete_item.return_value = True
    
    stats = purge_service.purge_notes(["P1"], phase="fulltext", dry_run=False)
    assert stats["deleted"] == 1
    mock_gateway.delete_item.assert_called_once_with("N2", 1)

def test_purge_tags_all(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=10, item_type="journalArticle", tags=["t1", "t2"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = True
    
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    
    assert stats["deleted"] == 1
    mock_gateway.update_item_metadata.assert_called_once_with("K1", 10, {"tags": []})

def test_purge_tags_specific(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=10, item_type="journalArticle", tags=["t1", "t2"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = True
    
    stats = purge_service.purge_tags(["K1"], tag_name="t1", dry_run=False)
    
    assert stats["deleted"] == 1
    mock_gateway.update_item_metadata.assert_called_once_with("K1", 10, {"tags": [{"tag": "t2"}]})

def test_offline_veto(purge_service, mock_gateway):
    # Mocking the class name to trigger _is_offline
    mock_gateway.__class__.__name__ = "SqliteZoteroGateway"
    
    with pytest.raises(RuntimeError, match="Offline Veto"):
        purge_service.purge_attachments(["K1"])
