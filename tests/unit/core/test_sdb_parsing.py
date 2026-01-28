import pytest
from zotero_cli.core.utils.sdb_parser import parse_sdb_note

def test_parse_simple_sdb():
    content = '{"audit_version": "1.2", "phase": "fulltext"}'
    data = parse_sdb_note(content)
    assert data is not None
    assert data["audit_version"] == "1.2"
    assert data["phase"] == "fulltext"

def test_parse_wrapped_in_div():
    content = '<div>{"action": "screening_decision", "persona": "Dr. Silas"}</div>'
    data = parse_sdb_note(content)
    assert data is not None
    assert data["action"] == "screening_decision"
    assert data["persona"] == "Dr. Silas"

def test_parse_with_newlines_and_spaces():
    content = """
    <div>
      {
        "sdb_version": "1.0", 
        "phase": "title"
      }
    </div>
    """
    data = parse_sdb_note(content)
    assert data is not None
    assert data["sdb_version"] == "1.0"
    assert data["phase"] == "title"

def test_parse_malformed_json():
    content = '<div>{"audit_version": "1.2", "phase": "oops... missing brace"</div>'
    data = parse_sdb_note(content)
    assert data is None

def test_parse_non_sdb_json():
    content = '<div>{"some_other_data": 123}</div>'
    data = parse_sdb_note(content)
    assert data is None

def test_parse_empty_or_none():
    assert parse_sdb_note("") is None
    assert parse_sdb_note(None) is None

def test_parse_legacy_format():
    # Legacy notes might not have the exact wrapper but should still parse if regex catches it
    content = 'SDB Meta: {"audit_version": "1.1", "phase": "p1"}'
    data = parse_sdb_note(content)
    assert data is not None
    assert data["phase"] == "p1"
