import pytest
from unittest.mock import MagicMock, patch
import requests
from zotero_cli.infra.dblp_api import DBLPAPIClient
from zotero_cli.core.models import ResearchPaper

@pytest.fixture
def client():
    return DBLPAPIClient()

def test_map_to_research_paper(client):
    info = {
        "title": "A Great CS Paper.",
        "authors": {
            "author": [
                {"text": "Knuth, Donald E."},
                {"text": "Dijkstra, Edsger W."}
            ]
        },
        "venue": "Journal of Algorithms",
        "year": "1980",
        "doi": "10.1000/cs123",
        "ee": "https://doi.org/10.1000/cs123"
    }
    paper = client._map_to_research_paper(info)
    assert paper.title == "A Great CS Paper" # Dot stripped
    assert paper.authors == ["Knuth, Donald E.", "Dijkstra, Edsger W."]
    assert paper.publication == "Journal of Algorithms"
    assert paper.year == "1980"
    assert paper.doi == "10.1000/cs123"
    assert paper.url == "https://doi.org/10.1000/cs123"

def test_map_to_research_paper_single_author(client):
    info = {
        "title": "Solo Paper",
        "authors": {"author": {"text": "Turing, Alan"}},
        "year": "1936"
    }
    paper = client._map_to_research_paper(info)
    assert paper.authors == ["Turing, Alan"]

def test_get_paper_metadata_success(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": {
            "hits": {
                "hit": [{"info": {"title": "Found Paper", "doi": "10.1/1"}}]
            }
        }
    }
    
    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("search query")
        assert paper.title == "Found Paper"
        args, kwargs = client._get.call_args
        assert kwargs["params"]["q"] == "search query"

def test_get_paper_metadata_not_found(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": {"hits": {}}}
    
    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("none")
        assert paper is None
