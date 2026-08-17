from unittest.mock import Mock, patch

import pytest

from zotero_cli.infra.semantic_scholar_api import SemanticScholarAPIClient

pytestmark = pytest.mark.usefixtures("no_sleep")


@pytest.fixture
def no_sleep():
    with patch("zotero_cli.infra.semantic_scholar_api.time.sleep"):
        yield


@pytest.fixture
def client():
    return SemanticScholarAPIClient()


@patch("requests.Session.get")
def test_get_paper_metadata_success(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "title": "S2 Title",
        "abstract": "S2 Abstract",
        "year": 2023,
        "venue": "NeurIPS",
        "authors": [{"name": "Author A"}, {"name": "Author B"}],
        "externalIds": {"DOI": "10.1234/s2", "ArXiv": "2301.00001"},
        "references": [
            {"externalIds": {"DOI": "10.5678/ref1"}},
            {"externalIds": {}},  # Ref without DOI
        ],
    }
    mock_get.return_value = mock_response

    metadata = client.get_paper_metadata("10.1234/s2")

    assert metadata is not None
    assert metadata.title == "S2 Title"
    assert metadata.abstract == "S2 Abstract"
    assert metadata.year == "2023"
    assert metadata.doi == "10.1234/s2"
    assert metadata.arxiv_id == "2301.00001"
    assert metadata.authors == ["Author A", "Author B"]
    assert metadata.references == ["10.5678/ref1"]


@patch("requests.Session.get")
def test_get_paper_metadata_not_found(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    metadata = client.get_paper_metadata("10.0000/missing")
    assert metadata is None


def _s2_paper(title: str) -> dict:
    return {
        "title": title,
        "abstract": "",
        "year": 2024,
        "venue": "",
        "authors": [],
        "externalIds": {},
    }


@patch("requests.Session.get")
def test_search_single_page(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "total": 2,
        "data": [_s2_paper("Paper A"), _s2_paper("Paper B")],
    }
    mock_get.return_value = mock_response

    results = list(client.search("attention mechanisms", max_results=10))

    assert len(results) == 2
    assert results[0].title == "Paper A"
    assert results[1].title == "Paper B"
    called_url, called_kwargs = mock_get.call_args.args, mock_get.call_args.kwargs
    assert "search" in called_url[0]
    assert called_kwargs["params"]["query"] == "attention mechanisms"
    assert called_kwargs["params"]["limit"] == 10


@patch("requests.Session.get")
def test_search_paginates_until_max_results(mock_get, client):
    page1 = Mock()
    page1.status_code = 200
    page1.json.return_value = {"total": 150, "data": [_s2_paper(f"P{i}") for i in range(100)]}
    page2 = Mock()
    page2.status_code = 200
    page2.json.return_value = {"total": 150, "data": [_s2_paper(f"P{i}") for i in range(100, 120)]}
    mock_get.side_effect = [page1, page2]

    results = list(client.search("topic", max_results=120))

    assert len(results) == 120
    assert mock_get.call_count == 2


@patch("requests.Session.get")
def test_search_stops_when_total_exhausted(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"total": 1, "data": [_s2_paper("Only Paper")]}
    mock_get.return_value = mock_response

    results = list(client.search("rare topic", max_results=100))

    assert len(results) == 1
    assert mock_get.call_count == 1


@patch("requests.Session.get")
def test_search_error_stops_iteration(mock_get, client):
    mock_get.side_effect = Exception("network error")

    results = list(client.search("topic"))

    assert results == []
