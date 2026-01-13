import pytest
import json
from unittest.mock import MagicMock
from zotero_cli.core.services.migration_service import MigrationService

@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def service(mock_gateway):
    return MigrationService(mock_gateway)

def test_migrate_note_content_removes_signature(service):
    legacy_note = '<div>{"signature": "Dr. Vance", "decision": "accepted", "agent": "vance-cli", "audit_version": "1.0"}</div>'
    new_note = service._migrate_note_content(legacy_note)
    
    data = json.loads(new_note.replace("<div>", "").replace("</div>", ""))
    assert "signature" not in data
    assert data["agent"] == "zotero-cli"
    assert data["persona"] == "vance-cli"
    assert data["audit_version"] == "1.1"

def test_migrate_note_content_standardizes_agent(service):
    legacy_note = '<div>{"decision": "accepted", "agent": "Manual TUI", "audit_version": "1.0"}</div>'
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
    legacy_note = '<div>{"decision": "rejected", "reason_code": "EC1, EC2", "audit_version": "1.0"}</div>'
    new_note = service._migrate_note_content(legacy_note)
    
    data = json.loads(new_note.replace("<div>", "").replace("</div>", ""))
    assert data["reason_code"] == ["EC1", "EC2"]

def test_migrate_note_no_changes_needed(service):
    clean_note = '<div>{\n  "audit_version": "1.1",\n  "decision": "accepted",\n  "reason_code": [],\n  "reason_text": "",\n  "timestamp": "2026-01-12T12:00:00Z",\n  "agent": "zotero-cli",\n  "persona": "test",\n  "phase": "title_abstract",\n  "action": "screening_decision"\n}</div>'
    # Use exact same content to verify no change
    new_note = service._migrate_note_content(clean_note)
    assert new_note == clean_note
