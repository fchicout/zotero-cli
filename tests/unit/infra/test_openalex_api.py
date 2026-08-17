from unittest.mock import MagicMock, patch

import pytest
import requests

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.openalex_api import OpenAlexAPIClient


@pytest.fixture
def client():
    return OpenAlexAPIClient(email="test@example.com")


def test_reconstruct_abstract(client):
    inverted_index = {"The": [0], "quick": [1], "brown": [2], "fox": [3]}
    abstract = client._reconstruct_abstract(inverted_index)
    assert abstract == "The quick brown fox"


def test_reconstruct_abstract_empty(client):
    assert client._reconstruct_abstract(None) == ""
    assert client._reconstruct_abstract({}) == ""


def test_get_paper_metadata_success(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "display_name": "Test Paper",
        "abstract_inverted_index": {"Abstract": [0]},
        "authorships": [{"author": {"display_name": "Author 1"}}],
        "primary_location": {"source": {"display_name": "Journal X"}},
        "publication_year": 2023,
        "doi": "https://doi.org/10.1000/123",
        "id": "https://openalex.org/W123",
        "best_oa_location": {"pdf_url": "http://example.com/test.pdf"},
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("10.1000/123")

        assert isinstance(paper, ResearchPaper)
        assert paper.title == "Test Paper"
        assert paper.abstract == "Abstract"
        assert paper.authors == ["Author 1"]
        assert paper.publication == "Journal X"
        assert paper.year == "2023"
        assert paper.pdf_url == "http://example.com/test.pdf"


def test_get_paper_metadata_not_found(client):
    mock_response = MagicMock()
    mock_response.status_code = 404
    error = requests.exceptions.HTTPError(response=mock_response)

    with patch.object(client, "_get", side_effect=error):
        paper = client.get_paper_metadata("non-existent")
        assert paper is None


def _openalex_work(display_name: str) -> dict:
    return {
        "display_name": display_name,
        "abstract_inverted_index": None,
        "authorships": [],
        "primary_location": {},
        "publication_year": 2024,
        "doi": None,
        "id": "https://openalex.org/W1",
        "best_oa_location": {},
    }


def test_search_single_page(client):
    page1 = MagicMock()
    page1.json.return_value = {"results": [_openalex_work("Paper A"), _openalex_work("Paper B")]}
    page2 = MagicMock()
    page2.json.return_value = {"results": []}

    with patch.object(client, "_get", side_effect=[page1, page2]) as mock_get:
        results = list(client.search("neural networks", max_results=10))

    assert len(results) == 2
    assert results[0].title == "Paper A"
    assert results[1].title == "Paper B"
    params = mock_get.call_args_list[0].kwargs["params"]
    assert params["search"] == "neural networks"
    assert params["per-page"] == 10
    assert "sort" not in params


def test_search_paginates_until_max_results(client):
    page1 = MagicMock()
    page1.json.return_value = {"results": [_openalex_work(f"P{i}") for i in range(200)]}
    page2 = MagicMock()
    page2.json.return_value = {"results": [_openalex_work("P200"), _openalex_work("P201")]}

    with patch.object(client, "_get", side_effect=[page1, page2]) as mock_get:
        results = list(client.search("topic", max_results=201))

    assert len(results) == 201
    assert mock_get.call_count == 2


def test_search_stops_on_empty_page(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}

    with patch.object(client, "_get", return_value=mock_response):
        results = list(client.search("no matches", max_results=50))

    assert results == []


def test_search_non_relevance_sort_sets_sort_param(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}

    with patch.object(client, "_get", return_value=mock_response) as mock_get:
        list(client.search("topic", sort_by="submittedDate", sort_order="ascending"))

    assert mock_get.call_args.kwargs["params"]["sort"] == "publication_date:asc"


def test_search_error_stops_iteration(client):
    with patch.object(client, "_get", side_effect=requests.exceptions.ConnectionError("boom")):
        results = list(client.search("topic"))

    assert results == []
