import json
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.migration_service import MigrationService


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def service(mock_gateway):
    return MigrationService(mock_gateway)


def test_migrate_note_content_removes_signature(service):
    legacy_note = '<div>{"signature": "Dr. Silas", "decision": "accepted", "agent": "vance-cli", "audit_version": "1.0"}</div>'
    new_note = service._migrate_note_content(legacy_note)

    data = json.loads(new_note.replace("<div>", "").replace("</div>", ""))
    assert "signature" not in data
    assert data["agent"] == "zotero-cli"
    assert data["persona"] == "vance-cli"
    assert data["audit_version"] == "1.1"


def test_migrate_note_content_standardizes_agent(service):
    legacy_note = (
        '<div>{"decision": "accepted", "agent": "Manual TUI", "audit_version": "1.0"}</div>'
    )
    new_note = service._migrate_note_content(legacy_note)

    data = json.loads(new_note.replace("<div>", "").replace("</div>", ""))
    assert data["agent"] == "zotero-cli"
    assert data["persona"] == "Manual TUI"


def test_migrate_note_content_handles_reason_code(service):
    legacy_note = '<div>{"decision": "rejected", "code": "EC1", "audit_version": "1.0"}</div>'
    new_note = service._migrate_note_content(legacy_note)

    data = json.loads(new_note.replace("<div>", "").replace("</div>", ""))
    assert data["reason_code"] == ["EC1"]
    assert "code" not in data


def test_migrate_note_content_handles_comma_separated_codes(service):
    legacy_note = (
        '<div>{"decision": "rejected", "reason_code": "EC1, EC2", "audit_version": "1.0"}</div>'
    )
    new_note = service._migrate_note_content(legacy_note)

    data = json.loads(new_note.replace("<div>", "").replace("</div>", ""))
    assert data["reason_code"] == ["EC1", "EC2"]


def test_migrate_note_no_changes_needed(service):
    clean_note = '<div>{\n  "audit_version": "1.1",\n  "decision": "accepted",\n  "reason_code": [],\n  "reason_text": "",\n  "timestamp": "2026-01-12T12:00:00Z",\n  "agent": "zotero-cli",\n  "persona": "test",\n  "phase": "title_abstract",\n  "action": "screening_decision"\n}</div>'
    # Use exact same content to verify no change
    new_note = service._migrate_note_content(clean_note)
    assert new_note == clean_note


def test_migrate_collection_notes_full_loop(service, mock_gateway):
    # Setup
    mock_gateway.get_collection_id_by_name.return_value = "col123"
    item = MagicMock()
    item.key = "item1"
    mock_gateway.get_items_in_collection.return_value = [item]

    note = {
        "key": "note1",
        "data": {
            "itemType": "note",
            "version": 1,
            "note": '<div>{"signature": "vance", "decision": "accepted"}</div>',
        },
    }
    mock_gateway.get_item_children.return_value = [note]
    mock_gateway.update_note.return_value = True

    # Execute
    stats = service.migrate_collection_notes("My Col", dry_run=False)

    # Verify
    assert stats["processed"] == 1
    assert stats["migrated"] == 1
    mock_gateway.update_note.assert_called_once()


def test_migrate_collection_notes_dry_run(service, mock_gateway):
    # Setup
    mock_gateway.get_collection_id_by_name.return_value = "col123"
    item = MagicMock()
    item.key = "item1"
    mock_gateway.get_items_in_collection.return_value = [item]

    note = {
        "key": "note1",
        "data": {
            "itemType": "note",
            "version": 1,
            "note": '<div>{"signature": "vance", "decision": "accepted"}</div>',
        },
    }
    mock_gateway.get_item_children.return_value = [note]

    # Execute
    stats = service.migrate_collection_notes("My Col", dry_run=True)

    # Verify
    assert stats["migrated"] == 1
    mock_gateway.update_note.assert_not_called()


def test_migrate_collection_not_found(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = None
    stats = service.migrate_collection_notes("Missing")
    assert stats["error"] == 1


def test_migrate_note_with_malformed_json(service):
    malformed = "<div>{not actually json}</div>"
    assert service._migrate_note_content(malformed) == malformed


def test_migrate_note_no_json(service):
    text = "Just some random note text"
    assert service._migrate_note_content(text) == text


def test_migrate_update_failure(service, mock_gateway):
    # Setup
    mock_gateway.get_collection_id_by_name.return_value = "col123"
    item = MagicMock()
    item.key = "item1"
    mock_gateway.get_items_in_collection.return_value = [item]
    mock_gateway.get_item_children.return_value = [
        {
            "key": "note1",
            "data": {"itemType": "note", "version": 1, "note": '<div>{"signature": "x"}</div>'},
        }
    ]
    mock_gateway.update_note.return_value = False  # Simulate API failure

    # Execute
    stats = service.migrate_collection_notes("My Col", dry_run=False)
    assert stats["failed"] == 1
