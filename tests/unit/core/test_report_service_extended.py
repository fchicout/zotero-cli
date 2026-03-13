from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.models import Job
from zotero_cli.core.services.report_service import PrismaReport, ReportService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()


def test_generate_prisma_report_missing_col(mock_gateway):
    service = ReportService(mock_gateway)
    mock_gateway.get_collection_id_by_name.return_value = None
    assert service.generate_prisma_report("Missing") is None


def test_generate_mermaid_prisma():
    report = PrismaReport(
        collection_name="Test",
        total_items=10,
        screened_items=5,
        accepted_items=3,
        rejected_items=2,
        rejections_by_code={"EC1": 1, "EC2": 1},
    )
    service = ReportService(MagicMock())
    mermaid = service.generate_mermaid_prisma(report)

    assert "graph TD" in mermaid
    assert "Identification: 10 items" in mermaid
    assert "Accepted: 3" in mermaid
    assert "Rejected: 2" in mermaid
    assert "E --> E0[EC1: 1]" in mermaid
    assert "E --> E1[EC2: 1]" in mermaid


def test_generate_screening_markdown():
    report = PrismaReport(
        collection_name="Test Collection",
        total_items=10,
        screened_items=5,
        accepted_items=3,
        rejected_items=2,
        rejections_by_code={"EC1": 2},
    )
    service = ReportService(MagicMock())
    md = service.generate_screening_markdown(report)

    assert "# Screening Report: Test Collection" in md
    assert "## 1. Executive Summary" in md
    assert "**Items Screened:** 5 (50.0%)" in md
    assert "| EC1 | 2 | 100.0% |" in md
    assert "## 3. PRISMA 2020 Flow Diagram" in md
    assert "```mermaid" in md


def test_generate_pdf_report():
    jobs = [
        Job(
            item_key="K1",
            task_type="fetch_pdf",
            status="COMPLETED",
            attempts=1,
            payload={"result": {"method": "unpaywall", "path": "/tmp/p1.pdf"}},
        ),
        Job(
            item_key="K2",
            task_type="fetch_pdf",
            status="FAILED",
            attempts=3,
            last_error="Timeout",
            payload={},
        ),
    ]
    service = ReportService(MagicMock())
    md = service.generate_pdf_report(jobs)

    assert "# PDF Discovery Report" in md
    assert "| K1 | COMPLETED | unpaywall | 1 | /tmp/p1.pdf |" in md
    assert "| K2 | FAILED | - | 3 | Timeout |" in md
    assert "**Total Jobs:** 2" in md
    assert "**Success:** 1" in md
    assert "**Failed:** 1" in md


@patch("subprocess.run")
def test_render_diagram_success(mock_run, tmp_path):
    mock_run.return_value.returncode = 0
    service = ReportService(MagicMock())
    output = str(tmp_path / "chart.png")

    assert service.render_diagram("graph TD", output) is True
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_render_diagram_failure(mock_run, tmp_path):
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "mmdc failed"
    service = ReportService(MagicMock())
    output = str(tmp_path / "chart.png")

    assert service.render_diagram("graph TD", output) is False


def test_render_diagram_exception():
    with patch("subprocess.run", side_effect=RuntimeError("no mmdc")):
        service = ReportService(MagicMock())
        assert service.render_diagram("graph TD", "out.png") is False


def test_process_item_notes_variations(mock_gateway):
    # Test different JSON formats in notes
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle")

    # Note with "include" decision and audit_version instead of action
    note1 = {"itemType": "note", "note": '{"audit_version": "1.2", "decision": "include"}'}
    # Note with "exclude" and "code" instead of "reason_code"
    note2 = {
        "itemType": "note",
        "note": 'Decision Block: {"action": "screening_decision", "decision": "exclude", "code": "EC1"}',
    }
    # Malformed note
    note3 = {"itemType": "note", "note": '{"bad_json": '}
    # Not an SDB note
    note4 = {"itemType": "note", "note": "Just a regular note"}

    mock_gateway.get_item_children.return_value = [note1, note2, note3, note4]

    report = PrismaReport(collection_name="Test")
    service = ReportService(mock_gateway)
    service._process_item_notes(item, report)

    assert report.screened_items == 1  # It breaks after finding the FIRST valid SDB note per item
    # Wait, the current logic in _process_item_notes calls break after processing ONE note.
    # Let's verify that.


def test_process_item_notes_multiple_items(mock_gateway):
    service = ReportService(mock_gateway)

    # Item 1: Accepted
    item1 = ZoteroItem(key="K1", version=1, item_type="journalArticle")
    mock_gateway.get_item_children.side_effect = [
        [{"itemType": "note", "note": '{"audit_version": "1.2", "decision": "accepted"}'}],
        [
            {
                "itemType": "note",
                "note": '{"audit_version": "1.2", "decision": "rejected", "reason_code": "EC9"}',
            }
        ],
        [
            {
                "itemType": "note",
                "note": '{"audit_version": "1.2", "decision": "rejected", "reason_code": ["EC1", "EC2"]}',
            }
        ],
    ]

    report = PrismaReport(collection_name="Test")
    service._process_item_notes(item1, report)

    # Item 2: Rejected with string reason_code
    item2 = ZoteroItem(key="K2", version=1, item_type="journalArticle")
    service._process_item_notes(item2, report)

    # Item 3: Rejected with list reason_code
    item3 = ZoteroItem(key="K3", version=1, item_type="journalArticle")
    service._process_item_notes(item3, report)

    assert report.accepted_items == 1
    assert report.rejected_items == 2
    assert report.screened_items == 3
    assert report.rejections_by_code["EC9"] == 1
    assert report.rejections_by_code["EC1"] == 1
    assert report.rejections_by_code["EC2"] == 1


def test_process_item_malformed_json(mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle")
    mock_gateway.get_item_children.return_value = [
        {"itemType": "note", "note": '{ "invalid": json, }'}  # Matches {.*} but invalid JSON
    ]
    report = PrismaReport(collection_name="Test")
    service = ReportService(mock_gateway)
    service._process_item_notes(item, report)

    assert report.malformed_notes == ["K1"]
