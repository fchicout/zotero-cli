import pytest
from unittest.mock import MagicMock, patch
import requests
from zotero_cli.infra.eric_api import ERICAPIClient
from zotero_cli.core.models import ResearchPaper

@pytest.fixture
def client():
    return ERICAPIClient()

def test_map_to_research_paper(client):
    item = {
        "title": "Educational Study",
        "description": "An abstract of the study.",
        "author": ["Smith, J.", "Doe, A."],
        "source": "Journal of Education",
        "pubyear": 2022,
        "doi": "10.1000/eric123",
        "id": "EJ123456",
        "peerreviewed": "T",
        "subject": ["Pedagogy", "Technology"]
    }
    paper = client._map_to_research_paper(item)
    assert paper.title == "Educational Study"
    assert paper.abstract == "An abstract of the study."
    assert paper.authors == ["Smith, J.", "Doe, A."]
    assert paper.publication == "Journal of Education"
    assert paper.year == "2022"
    assert paper.doi == "10.1000/eric123"
    assert "Peer Reviewed: Yes" in paper.extra
    assert "Subjects: Pedagogy, Technology" in paper.extra
    assert "eric.ed.gov/?id=EJ123456" in paper.url

def test_get_paper_metadata_ej(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": {
            "docs": [{"title": "EJ Paper", "id": "EJ1"}]
        }
    }
    
    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("EJ1")
        assert paper.title == "EJ Paper"
        args, kwargs = client._get.call_args
        assert "id:EJ1" in kwargs["params"]["search"]

def test_get_paper_metadata_ed(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": {
            "docs": [{"title": "ED Report", "id": "ED1"}]
        }
    }
    
    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("ED1")
        assert paper.title == "ED Report"

def test_get_paper_metadata_invalid_format(client):
    assert client.get_paper_metadata("DOI:10.1/1") is None
    assert client.get_paper_metadata("12345") is None

def test_get_paper_metadata_not_found(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": {"docs": []}}
    
    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("EJ404")
        assert paper is None
