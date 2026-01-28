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

def test_purge_attachments_error(purge_service, mock_gateway):
    mock_gateway.get_item_children.side_effect = Exception("API Error")
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    assert stats["errors"] == 1

def test_purge_notes_malformed_json(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "note": '{"bad json...', "version": 1}}
    ]
    # Should not crash, just skip/ignore as not SDB
    stats = purge_service.purge_notes(["P1"], sdb_only=True, dry_run=False)
    assert stats["deleted"] == 0
    assert stats["skipped"] == 0

def test_purge_tags_item_not_found(purge_service, mock_gateway):
    mock_gateway.get_item.return_value = None
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["errors"] == 1

def test_purge_tags_api_failure(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = False
    
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["errors"] == 1

def test_parse_sdb_info_no_json(purge_service):
    is_sdb, phase = purge_service._parse_sdb_info("Just plain text")
    assert is_sdb is False
    assert phase is None

def test_parse_sdb_info_sdb_version(purge_service):
    is_sdb, phase = purge_service._parse_sdb_info('{"sdb_version": "1.0", "phase": "test"}')
    assert is_sdb is True
    assert phase == "test"

def test_purge_attachments_error_handling(purge_service, mock_gateway):
    mock_gateway.get_item_children.side_effect = Exception("Network error")
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    assert stats["errors"] == 1

def test_purge_attachments_delete_failure(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 5}}
    ]
    mock_gateway.delete_item.return_value = False
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    assert stats["errors"] == 1

def test_purge_notes_error_handling(purge_service, mock_gateway):
    mock_gateway.get_item_children.side_effect = Exception("Network error")
    stats = purge_service.purge_notes(["P1"], dry_run=False)
    assert stats["errors"] == 1

def test_purge_notes_parse_failure(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "note": '{"invalid": json', "version": 1}}
    ]
    mock_gateway.delete_item.return_value = True
    # If parsing fails, it's not detected as SDB
    stats = purge_service.purge_notes(["P1"], sdb_only=True, dry_run=False)
    assert stats["deleted"] == 0

def test_purge_notes_no_match(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "note": "Plain text", "version": 1}}
    ]
    stats = purge_service.purge_notes(["P1"], sdb_only=True, dry_run=False)
    assert stats["deleted"] == 0

def test_purge_tags_no_tags(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=[])
    mock_gateway.get_item.return_value = item
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["deleted"] == 0

def test_purge_tags_not_present(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t2"])
    mock_gateway.get_item.return_value = item
    stats = purge_service.purge_tags(["K1"], tag_name="t1", dry_run=False)
    assert stats["deleted"] == 0

def test_purge_tags_update_failure(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = False
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["errors"] == 1

def test_purge_attachments_alternate_key(purge_service, mock_gateway):
    # Test line 46: key = child.get("key") or data.get("key")
    mock_gateway.get_item_children.return_value = [
        {"data": {"itemType": "attachment", "version": 5, "key": "A1"}}
    ]
    mock_gateway.delete_item.return_value = True
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    assert stats["deleted"] == 1

def test_purge_notes_alternate_key(purge_service, mock_gateway):
    # Test line 83: key = child.get("key") or data.get("key")
    mock_gateway.get_item_children.return_value = [
        {"data": {"itemType": "note", "version": 5, "key": "N1"}}
    ]
    mock_gateway.delete_item.return_value = True
    stats = purge_service.purge_notes(["P1"], dry_run=False)
    assert stats["deleted"] == 1

def test_purge_notes_only_phase(purge_service, mock_gateway):
    # Test branch line 75: if sdb_only or phase:
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "note": '{"phase": "p1"}', "version": 1}}
    ]
    mock_gateway.delete_item.return_value = True
    stats = purge_service.purge_notes(["P1"], phase="p1", dry_run=False)
    assert stats["deleted"] == 1

def test_purge_tags_all_branch(purge_service, mock_gateway):
    # Test line 123: else: new_tags = []
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = True
    stats = purge_service.purge_tags(["K1"], tag_name=None, dry_run=False)
    assert stats["deleted"] == 1

def test_offline_veto_notes(purge_service, mock_gateway):
    # Test line 61
    mock_gateway.__class__.__name__ = "SqliteZoteroGateway"
    with pytest.raises(RuntimeError, match="Offline Veto"):
        purge_service.purge_notes(["K1"])

def test_offline_veto_tags(purge_service, mock_gateway):
    # Test line 101
    mock_gateway.__class__.__name__ = "SqliteZoteroGateway"
    with pytest.raises(RuntimeError, match="Offline Veto"):
        purge_service.purge_tags(["K1"])

def test_purge_notes_dry_run(purge_service, mock_gateway):
    # Test line 83
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "version": 1}}
    ]
    stats = purge_service.purge_notes(["P1"], dry_run=True)
    assert stats["skipped"] == 1

def test_purge_notes_delete_failure(purge_service, mock_gateway):
    # Test line 88
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "version": 1}}
    ]
    mock_gateway.delete_item.return_value = False
    stats = purge_service.purge_notes(["P1"], dry_run=False)
    assert stats["errors"] == 1

def test_purge_tags_dry_run(purge_service, mock_gateway):
    # Test line 123
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    stats = purge_service.purge_tags(["K1"], dry_run=True)
    assert stats["skipped"] == 1

def test_purge_tags_exception_line_131(purge_service, mock_gateway):
    # Ensure line 131 is hit
    mock_gateway.get_item.side_effect = Exception("Crash")
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["errors"] == 1

def test_parse_sdb_info_json_error(purge_service):
    # Test lines 150-151: except json.JSONDecodeError:
    is_sdb, phase = purge_service._parse_sdb_info("{ invalid }")
    assert is_sdb is False
    assert phase is None

def test_purge_item_assets(purge_service, mock_gateway):
    # Setup for multiple assets
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 1}},
        {"key": "N1", "data": {"itemType": "note", "version": 1}}
    ]
    item = ZoteroItem(key="P1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    
    mock_gateway.delete_item.return_value = True
    mock_gateway.update_item_metadata.return_value = True
    
    # Execute for all types
    stats = purge_service.purge_item_assets("P1", types=["files", "notes", "tags"], dry_run=False)
    
    assert stats["deleted"] == 3  # 1 attachment, 1 note, 1 tag update
    
    # Verify calls
    mock_gateway.delete_item.assert_any_call("A1", 1)
    mock_gateway.delete_item.assert_any_call("N1", 1)
    mock_gateway.update_item_metadata.assert_called_with("P1", 1, {"tags": []})

def test_purge_collection_assets(purge_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "C1"
    
    item1 = ZoteroItem(key="P1", version=1, item_type="journalArticle", tags=["t1"])
    item2 = ZoteroItem(key="P2", version=1, item_type="journalArticle", tags=[])
    
    mock_gateway.get_items_in_collection.return_value = [item1, item2]
    
    # Setup item children (attachments/notes) for P1 and P2
    # This mock needs to handle multiple calls differently if we want precise accounting,
    # but for simple verification, we can just return a fixed list or use side_effect.
    # P1 has 1 attachment. P2 has none.
    def get_children(key):
        if key == "P1":
            return [{"key": "A1", "data": {"itemType": "attachment", "version": 1}}]
        return []
    
    mock_gateway.get_item_children.side_effect = get_children
    
    # P1 has tags. P2 has none.
    def get_item(key):
        if key == "P1":
            return item1
        return item2
    mock_gateway.get_item.side_effect = get_item
    
    mock_gateway.delete_item.return_value = True
    mock_gateway.update_item_metadata.return_value = True
    
    stats = purge_service.purge_collection_assets("TestCollection", types=["files", "tags"], dry_run=False)
    
    # P1: 1 attachment deleted, 1 tag update = 2
    # P2: 0 attachments, 0 tags = 0
    assert stats["deleted"] == 2
    
    mock_gateway.get_collection_id_by_name.assert_called_with("TestCollection")
    mock_gateway.get_items_in_collection.assert_called_with("C1", recursive=False)

def test_purge_collection_not_found(purge_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = None
    stats = purge_service.purge_collection_assets("Unknown", dry_run=False)
    assert stats["errors"] == 1