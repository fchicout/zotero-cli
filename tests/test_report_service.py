import pytest
from unittest.mock import MagicMock
import json
from zotero_cli.core.services.report_service import ReportService
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def report_service(mock_gateway):
    return ReportService(mock_gateway)

def test_generate_prisma_report_success(report_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "COL_ID"
    
    item1 = ZoteroItem(key="K1", version=1, item_type="journalArticle")
    item2 = ZoteroItem(key="K2", version=1, item_type="journalArticle")
    item3 = ZoteroItem(key="K3", version=1, item_type="journalArticle")
    
    mock_gateway.get_items_in_collection.return_value = [item1, item2, item3]
    
    # K1: Accepted (Audit v1.1)
    note1 = {
        "itemType": "note",
        "note": '<div>{"audit_version": "1.1", "decision": "accepted", "action": "screening_decision"}</div>'
    }
    # K2: Rejected (Legacy format)
    note2 = {
        "itemType": "note",
        "note": '<div>{"action": "screening_decision", "decision": "EXCLUDE", "code": "EC01"}</div>'
    }
    # K3: No decision note
    
    mock_gateway.get_item_children.side_effect = [
        [note1],
        [note2],
        []
    ]
    
    report = report_service.generate_prisma_report("Test Col")
    
    assert report.total_items == 3
    assert report.screened_items == 2
    assert report.accepted_items == 1
    assert report.rejected_items == 1
    assert report.rejections_by_code["EC01"] == 1

def test_generate_prisma_report_malformed(report_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "COL_ID"
    item1 = ZoteroItem(key="K1", version=1, item_type="journalArticle")
    mock_gateway.get_items_in_collection.return_value = [item1]
    
    note1 = {
        "itemType": "note",
        "note": '<div>{"audit_version": "1.1", "decision": "accepted", malformed...}</div>'
    }
    mock_gateway.get_item_children.return_value = [note1]
    
    report = report_service.generate_prisma_report("Test Col")
    
    assert report.screened_items == 0
    assert len(report.malformed_notes) == 1
    assert report.malformed_notes[0] == "K1"

def test_generate_mermaid_prisma(report_service):
    from zotero_cli.core.services.report_service import PrismaReport
    report = PrismaReport(
        collection_name="Test",
        total_items=100,
        screened_items=80,
        accepted_items=30,
        rejected_items=50,
        rejections_by_code={"EC1": 40, "EC2": 10}
    )
    
    mermaid = report_service.generate_mermaid_prisma(report)
    assert "graph TD" in mermaid
    assert "Identification: 100 items" in mermaid
    assert "Screening: 80 items" in mermaid
    assert "Accepted: 30" in mermaid
    assert "Rejected: 50" in mermaid
    assert "EC1: 40" in mermaid
    assert "EC2: 10" in mermaid
