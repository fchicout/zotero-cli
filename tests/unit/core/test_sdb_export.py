from unittest.mock import MagicMock

from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.export_service import ExportService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.bibtex_lib import BibtexLibGateway


def test_export_service_with_sdb():
    """Verify ExportService fetches SDB metadata from SDBService."""
    mock_gateway = MagicMock()
    mock_bibtex = MagicMock()
    mock_sdb = MagicMock()
    service = ExportService(mock_gateway, mock_bibtex, mock_sdb)

    # Setup mocks
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="Test", authors=["A1"])
    mock_gateway.get_items_in_collection.return_value = iter([item])

    sdb_entry = {
        "decision": "accepted",
        "persona": "Sullivan",
        "phase": "screening",
        "reason_code": ["CODE1"],
        "reason_text": "Good paper",
        "evidence": "Found in title",
    }
    mock_sdb.inspect_item_sdb.return_value = [sdb_entry]
    mock_bibtex.write_file.return_value = True

    # Execute
    service.export_collection("MyCol", "out.bib")

    # Verify
    mock_sdb.inspect_item_sdb.assert_called_once_with("K1")
    papers = mock_bibtex.write_file.call_args[0][1]
    assert len(papers) == 1
    assert papers[0].sdb_metadata == [sdb_entry]


def test_bibtex_gateway_sdb_mapping():
    """Verify BibtexLibGateway maps SDB metadata to custom BibTeX fields."""
    gateway = BibtexLibGateway()
    sdb_entry1 = {
        "decision": "accepted",
        "persona": "Sullivan",
        "phase": "screening",
        "reason_code": ["CODE1"],
        "reason_text": "Text 1",
        "evidence": "Evidence 1",
    }
    sdb_entry2 = {
        "decision": "rejected",
        "persona": "Hamilton",
        "phase": "full-text",
        "reason_code": ["CODE2"],
        "reason_text": "Text 2",
        "evidence": "Evidence 2",
    }

    paper = ResearchPaper(
        title="Test", abstract="", authors=["Auth"], sdb_metadata=[sdb_entry1, sdb_entry2]
    )

    # Execute mapping via private method for direct verification
    entry = gateway._map_paper_to_entry(paper)

    # Verify first entry mapping (no suffix)
    assert entry["x-sdb-decision"] == "accepted"
    assert entry["x-sdb-reviewer"] == "Sullivan"
    assert entry["x-sdb-criteria"] == "CODE1"
    assert entry["x-sdb-phase"] == "screening"

    # Verify second entry mapping (suffix _2)
    assert entry["x-sdb-decision_2"] == "rejected"
    assert entry["x-sdb-reviewer_2"] == "Hamilton"
    assert entry["x-sdb-criteria_2"] == "CODE2"
    assert entry["x-sdb-phase_2"] == "full-text"

    # Verify standard note field summary
    assert "[Sullivan/screening] ACCEPTED: CODE1" in entry["note"]
    assert "[Hamilton/full-text] REJECTED: CODE2" in entry["note"]
