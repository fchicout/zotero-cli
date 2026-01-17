from unittest.mock import Mock, mock_open, patch

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.bibtex_lib import BibtexLibGateway


@patch("zotero_cli.infra.bibtex_lib.bibtexparser.load")
@patch("builtins.open", new_callable=mock_open)
def test_parse_file_success(mock_file, mock_load):
    # Setup mock BibDatabase
    mock_db = Mock()
    mock_db.entries = [
        {
            "title": "{My Paper}",
            "author": "Doe, John and Smith, Jane",
            "year": "2023",
            "journal": "Journal of AI",
            "doi": "10.1000/1",
            "abstract": "Abstract here",
        },
        {
            "title": "Another Paper",
            "author": "Single Author",
            "eprint": "2301.00001",
            "archivePrefix": "arXiv",
        },
    ]
    mock_load.return_value = mock_db

    gateway = BibtexLibGateway()
    papers = list(gateway.parse_file("test.bib"))

    assert len(papers) == 2

    assert isinstance(papers[0], ResearchPaper)
    assert papers[0].title == "My Paper"
    assert papers[0].authors == ["Doe, John", "Smith, Jane"]
    assert papers[0].year == "2023"
    assert papers[0].publication == "Journal of AI"
    assert papers[0].doi == "10.1000/1"

    assert isinstance(papers[1], ResearchPaper)
    assert papers[1].authors == ["Single Author"]
    assert papers[1].arxiv_id == "2301.00001"
