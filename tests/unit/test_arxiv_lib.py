from unittest.mock import MagicMock, Mock, patch

import arxiv

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.arxiv_lib import ArxivLibGateway


@patch("zotero_cli.infra.arxiv_lib.arxiv.Client")
@patch("zotero_cli.infra.arxiv_lib.arxiv.Search")
def test_search_returns_papers(MockSearch, MockClient):
    # Setup mocks
    mock_client_instance = MockClient.return_value

    # Create mock result objects that mimic arxiv.Result
    mock_result1 = MagicMock()
    mock_result1.get_short_id.return_value = "2301.00001v1"
    mock_result1.title = "Title 1"
    mock_result1.summary = "Abstract 1"
    mock_result1.authors = [Mock(), Mock()]
    mock_result1.authors[0].name = "Author 1"
    mock_result1.authors[1].name = "Author 2"
    mock_result1.published.year = 2023
    mock_result1.doi = "10.1234/doi1"
    mock_result1.pdf_url = "http://pdf1"
    mock_result1.journal_ref = "Journal 1"

    mock_result2 = MagicMock()
    mock_result2.get_short_id.return_value = "2301.00002v1"
    mock_result2.title = "Title 2"
    mock_result2.summary = "Abstract 2"
    mock_result2.authors = []
    mock_result2.published = None
    mock_result2.doi = None
    mock_result2.pdf_url = None
    mock_result2.journal_ref = None

    # The client.results() returns an iterator
    mock_client_instance.results.return_value = iter([mock_result1, mock_result2])

    # Action
    gateway = ArxivLibGateway()
    papers = list(gateway.search("test query", limit=2))

    # Assertion
    assert len(papers) == 2

    assert isinstance(papers[0], ResearchPaper)
    assert papers[0].arxiv_id == "2301.00001v1"
    assert papers[0].title == "Title 1"
    assert papers[0].abstract == "Abstract 1"
    assert papers[0].authors == ["Author 1", "Author 2"]
    assert papers[0].year == "2023"
    assert papers[0].doi == "10.1234/doi1"
    assert papers[0].url == "http://pdf1"
    assert papers[0].publication == "Journal 1"

    assert isinstance(papers[1], ResearchPaper)
    assert papers[1].arxiv_id == "2301.00002v1"
    assert papers[1].year is None

    # Verify arguments to arxiv.Search
    MockSearch.assert_called_once_with(
        query="test query",
        max_results=2,
        sort_by=arxiv.SortCriterion.Relevance,
        sort_order=arxiv.SortOrder.Descending,
    )


@patch("zotero_cli.infra.arxiv_lib.arxiv.Client")
@patch("zotero_cli.infra.arxiv_lib.arxiv.Search")
def test_search_extracts_doi_from_comment(MockSearch, MockClient):
    mock_client_instance = MockClient.return_value

    mock_result = MagicMock()
    mock_result.get_short_id.return_value = "2103.10433"
    mock_result.title = "Title"
    mock_result.summary = "Summary"
    mock_result.authors = []
    mock_result.published = None
    mock_result.doi = None  # Missing DOI field
    mock_result.comment = "Accepted at NeurIPS 2021. DOI: 10.1145/3442188.3445922"
    mock_result.journal_ref = None
    mock_result.pdf_url = "http://pdf"

    mock_client_instance.results.return_value = iter([mock_result])

    gateway = ArxivLibGateway()
    papers = list(gateway.search("query", limit=1))

    assert len(papers) == 1
    assert papers[0].doi == "10.1145/3442188.3445922"


@patch("zotero_cli.infra.arxiv_lib.arxiv.Client")
@patch("zotero_cli.infra.arxiv_lib.arxiv.Search")
def test_search_extracts_doi_from_journal_ref(MockSearch, MockClient):
    mock_client_instance = MockClient.return_value

    mock_result = MagicMock()
    mock_result.get_short_id.return_value = "2103.10433"
    mock_result.title = "Title"
    mock_result.summary = "Summary"
    mock_result.authors = []
    mock_result.published = None
    mock_result.doi = None
    mock_result.comment = None
    mock_result.journal_ref = "Nature 2021, doi:10.1038/s41586-021-03354-4"
    mock_result.pdf_url = "http://pdf"

    mock_client_instance.results.return_value = iter([mock_result])

    gateway = ArxivLibGateway()
    papers = list(gateway.search("query", limit=1))

    assert len(papers) == 1
    assert papers[0].doi == "10.1038/s41586-021-03354-4"
