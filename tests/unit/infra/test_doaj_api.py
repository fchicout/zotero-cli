from unittest.mock import MagicMock, patch

import pytest
import requests

from zotero_cli.infra.doaj_api import DOAJAPIClient


@pytest.fixture
def client():
    return DOAJAPIClient()


def _doaj_article(title: str, doi: str | None = None) -> dict:
    return {
        "id": "doaj123",
        "bibjson": {
            "title": title,
            "abstract": "An abstract.",
            "author": [{"name": "Author One"}],
            "year": "2024",
            "identifier": [{"type": "doi", "id": doi}] if doi else [],
            "link": [{"type": "fulltext", "url": "https://example.com/article.pdf"}],
            "journal": {"title": "Journal of Examples"},
        },
    }


def test_get_paper_metadata_success(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [_doaj_article("Open Access Paper", doi="10.1234/doaj")]
    }

    with patch.object(client, "_get", return_value=mock_response) as mock_get:
        paper = client.get_paper_metadata("10.1234/doaj")

    assert paper is not None
    assert paper.title == "Open Access Paper"
    assert paper.authors == ["Author One"]
    assert paper.year == "2024"
    assert paper.doi == "10.1234/doaj"
    assert paper.publication == "Journal of Examples"
    assert paper.url == "https://example.com/article.pdf"
    called_kwargs = mock_get.call_args.kwargs
    assert called_kwargs["endpoint"] == "10.1234%2Fdoaj"


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
        assert client.get_paper_metadata("missing") is None


def test_search_single_page(client):
    page1 = MagicMock()
    page1.json.return_value = {
        "total": 2,
        "results": [_doaj_article("Paper A"), _doaj_article("Paper B")],
    }
    page2 = MagicMock()
    page2.json.return_value = {"total": 2, "results": []}

    with patch.object(client, "_get", side_effect=[page1, page2]) as mock_get:
        results = list(client.search("open science", max_results=10))

    assert len(results) == 2
    assert results[0].title == "Paper A"
    params = mock_get.call_args_list[0].kwargs["params"]
    assert params["page"] == 1
    assert params["pageSize"] == 10


def test_search_paginates_until_max_results(client):
    page1 = MagicMock()
    page1.json.return_value = {"total": 102, "results": [_doaj_article(f"P{i}") for i in range(100)]}
    page2 = MagicMock()
    page2.json.return_value = {"total": 102, "results": [_doaj_article("P100"), _doaj_article("P101")]}

    with patch.object(client, "_get", side_effect=[page1, page2]) as mock_get:
        results = list(client.search("topic", max_results=102))

    assert len(results) == 102
    assert mock_get.call_count == 2


def test_search_stops_on_empty_page(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"total": 0, "results": []}

    with patch.object(client, "_get", return_value=mock_response):
        results = list(client.search("no matches"))

    assert results == []


def test_search_error_stops_iteration(client):
    with patch.object(client, "_get", side_effect=requests.exceptions.ConnectionError("boom")):
        results = list(client.search("topic"))

    assert results == []


def test_count_returns_total(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"total": 4242, "results": [_doaj_article("Only")]}

    with patch.object(client, "_get", return_value=mock_response) as mock_get:
        total = client.count("open science")

    assert total == 4242
    assert mock_get.call_args.kwargs["params"]["pageSize"] == 1


def test_count_error_returns_zero(client):
    with patch.object(client, "_get", side_effect=Exception("boom")):
        assert client.count("topic") == 0
