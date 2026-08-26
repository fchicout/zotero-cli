from unittest.mock import MagicMock, patch

import pytest
import requests

from zotero_cli.infra.core_api import CoreAPIClient


@pytest.fixture
def client():
    return CoreAPIClient(api_key="test_key")


def _core_work(title: str, doi: str | None = None) -> dict:
    return {
        "title": title,
        "abstract": "",
        "authors": [{"name": "Author One"}],
        "yearPublished": 2024,
        "doi": doi,
        "publisher": "Some Publisher",
        "downloadUrl": "http://core.ac.uk/download/1.pdf",
    }


def test_init_sets_authorization_header():
    client = CoreAPIClient(api_key="my_key")
    assert client.session.headers.get("Authorization") == "Bearer my_key"


def test_init_without_key_has_no_authorization_header():
    client = CoreAPIClient()
    assert "Authorization" not in client.session.headers


def test_get_paper_metadata_by_numeric_id(client):
    mock_response = MagicMock()
    mock_response.json.return_value = _core_work("Numeric ID Paper")

    with patch.object(client, "_get", return_value=mock_response) as mock_get:
        paper = client.get_paper_metadata("12345")

    assert paper is not None
    assert paper.title == "Numeric ID Paper"
    assert paper.authors == ["Author One"]
    assert paper.year == "2024"
    assert paper.pdf_url == "http://core.ac.uk/download/1.pdf"
    assert mock_get.call_args.kwargs["endpoint"] == "works/12345"


def test_get_paper_metadata_by_doi(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [_core_work("DOI Paper", doi="10.1234/core")]
    }

    with patch.object(client, "_get", return_value=mock_response) as mock_get:
        paper = client.get_paper_metadata("10.1234/core")

    assert paper is not None
    assert paper.title == "DOI Paper"
    assert paper.doi == "10.1234/core"
    assert mock_get.call_args.kwargs["endpoint"] == "search/works"
    assert '10.1234/core' in mock_get.call_args.kwargs["params"]["q"]


def test_get_paper_metadata_not_found(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}

    with patch.object(client, "_get", return_value=mock_response):
        assert client.get_paper_metadata("10.0000/missing") is None


def test_get_paper_metadata_404(client):
    mock_response = MagicMock()
    mock_response.status_code = 404
    error = requests.exceptions.HTTPError(response=mock_response)

    with patch.object(client, "_get", side_effect=error):
        assert client.get_paper_metadata("999999") is None


def test_search_single_page(client):
    page1 = MagicMock()
    page1.json.return_value = {"results": [_core_work("Paper A"), _core_work("Paper B")]}
    page2 = MagicMock()
    page2.json.return_value = {"results": []}

    with patch.object(client, "_get", side_effect=[page1, page2]) as mock_get:
        results = list(client.search("machine learning", max_results=10))

    assert len(results) == 2
    assert results[0].title == "Paper A"
    params = mock_get.call_args_list[0].kwargs["params"]
    assert params["q"] == "machine learning"
    assert params["limit"] == 10


def test_search_paginates_until_max_results(client):
    page1 = MagicMock()
    page1.json.return_value = {"results": [_core_work(f"P{i}") for i in range(100)]}
    page2 = MagicMock()
    page2.json.return_value = {"results": [_core_work("P100"), _core_work("P101")]}

    with patch.object(client, "_get", side_effect=[page1, page2]) as mock_get:
        results = list(client.search("topic", max_results=102))

    assert len(results) == 102
    assert mock_get.call_count == 2


def test_search_stops_on_empty_page(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}

    with patch.object(client, "_get", return_value=mock_response):
        results = list(client.search("no matches"))

    assert results == []


def test_search_error_stops_iteration(client):
    with patch.object(client, "_get", side_effect=requests.exceptions.ConnectionError("boom")):
        results = list(client.search("topic"))

    assert results == []


def test_count_returns_total_hits(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"totalHits": 999, "results": [_core_work("Only")]}

    with patch.object(client, "_get", return_value=mock_response) as mock_get:
        total = client.count("machine learning")

    assert total == 999
    assert mock_get.call_args.kwargs["params"]["limit"] == 1


def test_count_error_returns_zero(client):
    with patch.object(client, "_get", side_effect=Exception("boom")):
        assert client.count("topic") == 0
