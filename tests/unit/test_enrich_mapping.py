from unittest.mock import Mock, patch
import pytest
from zotero_cli.core.services.audit_service import CollectionAuditor
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_gateway():
    return Mock()

@pytest.fixture
def auditor(mock_gateway):
    return CollectionAuditor(mock_gateway)

def create_mock_item(key, title=None, doi=None):
    raw_item = {
        "key": key,
        "data": {
            "version": 1,
            "itemType": "journalArticle",
            "title": title,
            "DOI": doi,
        },
    }
    return ZoteroItem.from_raw_zotero_item(raw_item)

def test_enrich_from_csv_custom_mapping(auditor, mock_gateway, tmp_path):
    csv_file = tmp_path / "custom_decisions.csv"
    # Custom headers: UID instead of Key, Decision instead of Vote, Justification instead of Reason
    csv_file.write_text(
        "UID,Decision,Justification,Error_Code\n"
        "KEY1,INCLUDE,Relevant study,IC1\n"
    )

    item1 = create_mock_item("KEY1", title="Paper A")
    mock_gateway.search_items.return_value = iter([item1])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    column_map = {
        "key": "UID",
        "vote": "Decision",
        "reason": "Justification",
        "code": "Error_Code"
    }

    results = auditor.enrich_from_csv(
        str(csv_file), 
        reviewer="Orion", 
        dry_run=False, 
        force=True,
        column_map=column_map
    )

    assert "error" not in results
    assert results["matched"] == 1
    assert results["created"] == 1
    
    # Verify the created note has the correct data
    args, _ = mock_gateway.create_note.call_args
    note_content = args[1]
    assert '"decision": "accepted"' in note_content
    assert '"reason_code": [\n    "IC1"\n  ]' in note_content or '"reason_code": ["IC1"]' in note_content.replace(" ", "").replace("\n", "")
    assert '"reason_text": "Relevant study"' in note_content

def test_enrich_from_csv_missing_mapped_column(auditor, mock_gateway, tmp_path):
    csv_file = tmp_path / "missing_cols.csv"
    csv_file.write_text("UID,Decision\nKEY1,INCLUDE\n")

    column_map = {
        "key": "UID",
        "vote": "Decision",
        "reason": "Missing_Col"
    }

    results = auditor.enrich_from_csv(
        str(csv_file), 
        reviewer="Orion", 
        column_map=column_map
    )

    assert "error" in results
    assert "Missing required columns in CSV: Missing_Col" in results["error"]

def test_enrich_from_csv_backward_compatibility(auditor, mock_gateway, tmp_path):
    # Standard format without explicit mapping
    csv_file = tmp_path / "standard.csv"
    csv_file.write_text(
        "Key,Vote,Reason,Code\n"
        "KEY1,INCLUDE,Standard Reason,IC1\n"
    )

    item1 = create_mock_item("KEY1", title="Paper A")
    mock_gateway.search_items.return_value = iter([item1])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    results = auditor.enrich_from_csv(
        str(csv_file), 
        reviewer="Orion", 
        dry_run=False, 
        force=True
    )

    assert "error" not in results
    assert results["matched"] == 1
    assert results["created"] == 1
    
    args, _ = mock_gateway.create_note.call_args
    note_content = args[1]
    assert '"decision": "accepted"' in note_content
    assert '"reason_text": "Standard Reason"' in note_content
