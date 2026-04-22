from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.infra.zbmath_api import zbMATHAPIClient


@pytest.fixture
def client():
    return zbMATHAPIClient()

def test_map_to_research_paper(client):
    item = {
        "title": "A Mathematical Paper",
        "review": "This is an abstract.",
        "authors": [{"name": "Euler, Leonhard"}, "Gauss, Carl"],
        "source": "Annals of Math",
        "year": 1750,
        "doi": "10.1000/math123",
        "zbl_id": "123.456"
    }
    paper = client._map_to_research_paper(item)
    assert paper.title == "A Mathematical Paper"
    assert paper.abstract == "This is an abstract."
    assert paper.authors == ["Euler, Leonhard", "Gauss, Carl"]
    assert paper.publication == "Annals of Math"
    assert paper.year == "1750"
    assert paper.doi == "10.1000/math123"
    assert "zbmath.org" in paper.url

def test_get_paper_metadata_doi(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [{"title": "Paper by DOI", "doi": "10.1/1"}]
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("10.1/1")
        assert paper.title == "Paper by DOI"
        # Check if query was formatted correctly
        args, kwargs = client._get.call_args
        assert "doi:10.1/1" in kwargs["params"]["q"]

def test_get_paper_metadata_zbl(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [{"title": "Paper by Zbl", "zbl_id": "123.456"}]
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("123.456")
        assert paper.title == "Paper by Zbl"
        args, kwargs = client._get.call_args
        assert "an:123.456" in kwargs["params"]["q"]

def test_get_paper_metadata_not_found(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("none")
        assert paper is None
