from unittest.mock import Mock

import pytest

from zotero_cli.core.services.sdb.sdb_service import SDBService


@pytest.fixture
def mock_gateway():
    return Mock()


@pytest.fixture
def service(mock_gateway):
    return SDBService(mock_gateway)


def test_inspect_item_sdb(service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {
            "key": "N1",
            "version": 10,
            "data": {
                "itemType": "note",
                "note": '<div>{"audit_version": "1.2", "decision": "accepted", "persona": "P1", "phase": "ph1"}</div>',
            },
        },
        {"key": "N2", "data": {"itemType": "note", "note": "regular note"}},
    ]

    entries = service.inspect_item_sdb("ITEM1")
    assert len(entries) == 1
    assert entries[0]["decision"] == "accepted"
    assert entries[0]["_note_key"] == "N1"
    assert entries[0]["_note_version"] == 10


def test_build_inspect_table(service):
    entries = [
        {
            "decision": "accepted",
            "persona": "P1",
            "phase": "ph1",
            "audit_version": "1.2",
            "timestamp": "2026-01-01",
        }
    ]
    table = service.build_inspect_table("ITEM1", entries)
    assert table.title == "SDB Inspect: ITEM1"
    assert len(table.rows) == 1


def test_edit_sdb_entry_success(service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {
            "key": "N1",
            "version": 10,
            "data": {
                "itemType": "note",
                "note": '<div>{"audit_version": "1.2", "decision": "accepted", "persona": "P1", "phase": "ph1"}</div>',
            },
        }
    ]
    mock_gateway.update_note.return_value = True

    success, msg = service.edit_sdb_entry(
        "ITEM1", "P1", "ph1", {"decision": "rejected"}, dry_run=False
    )

    assert success is True
    assert "Successfully updated" in msg
    mock_gateway.update_note.assert_called_once()
    args = mock_gateway.update_note.call_args[0]
    assert args[0] == "N1"
    assert '"decision": "rejected"' in args[2]


def test_edit_sdb_entry_not_found(service, mock_gateway):
    mock_gateway.get_item_children.return_value = []
    success, msg = service.edit_sdb_entry("ITEM1", "P1", "ph1", {"decision": "rejected"})
    assert success is False
    assert "No SDB entry found" in msg


def test_upgrade_sdb_entries(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_item = Mock()
    mock_item.key = "ITEM1"
    mock_gateway.get_items_in_collection.return_value = [mock_item]

    mock_gateway.get_item_children.return_value = [
        {
            "key": "N1",
            "version": 10,
            "data": {
                "itemType": "note",
                "note": '<div>{"audit_version": "1.0", "decision": "accepted", "persona": "P1", "phase": "ph1", "comment": "Old comment"}</div>',
            },
        }
    ]
    mock_gateway.update_note.return_value = True

    stats = service.upgrade_sdb_entries("Collection1", dry_run=False)

    assert stats["scanned"] == 1
    assert stats["upgraded"] == 1
    mock_gateway.update_note.assert_called_once()
    args = mock_gateway.update_note.call_args[0]
    assert '"audit_version": "1.2"' in args[2]
    assert '"reason_text": "Old comment"' in args[2]
