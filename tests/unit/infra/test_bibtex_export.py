import os
import tempfile
from unittest.mock import MagicMock

from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.export_service import ExportService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.bibtex_lib import BibtexLibGateway


def test_bibtex_export_roundtrip():
    """Verify round-trip: Paper -> BibTeX -> Paper."""
    gateway = BibtexLibGateway()
    paper = ResearchPaper(
        title="Scaling Laws for Neural Language Models",
        abstract="We study the empirical scaling laws...",
        authors=["Jared Kaplan", "Sam McCandlish"],
        year="2020",
        doi="10.48550/arXiv.2001.08361",
        arxiv_id="2001.08361",
    )
    paper.key = "kaplan2020scaling"

    with tempfile.NamedTemporaryFile(suffix=".bib", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Export
        success = gateway.write_file(tmp_path, [paper])
        assert success is True

        # Import back
        imported_papers = list(gateway.parse_file(tmp_path))
        assert len(imported_papers) == 1
        imported = imported_papers[0]

        assert imported.title == paper.title
        assert imported.authors == paper.authors
        assert imported.year == paper.year
        assert imported.doi == paper.doi
        assert imported.arxiv_id == paper.arxiv_id
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_export_service_logic():
    """Verify ExportService orchestrates the gateway correctly."""
    mock_gateway = MagicMock()
    mock_bibtex = MagicMock()
    mock_sdb = MagicMock()
    service = ExportService(mock_gateway, mock_bibtex, mock_sdb)

    # Setup mocks
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = ZoteroItem(
        key="K1",
        version=1,
        item_type="journalArticle",
        title="Test",
        authors=["A1"],
        date="2023-01-01",
    )
    item.raw_data = {"data": {"publicationTitle": "Journal X"}}
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_bibtex.write_file.return_value = True
    mock_sdb.inspect_item_sdb.return_value = []

    # Execute
    success = service.export_collection("MyCol", "out.bib")

    # Verify
    assert success is True
    mock_gateway.get_collection_id_by_name.assert_called_once_with("MyCol")
    mock_sdb.inspect_item_sdb.assert_called_once_with("K1")
    mock_bibtex.write_file.assert_called_once()
    papers = mock_bibtex.write_file.call_args[0][1]
    assert len(papers) == 1
    assert papers[0].title == "Test"
    assert papers[0].year == "2023"
    assert papers[0].publication == "Journal X"
