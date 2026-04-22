from unittest.mock import MagicMock, patch

import pytest
import requests

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.openalex_api import OpenAlexAPIClient


@pytest.fixture
def client():
    return OpenAlexAPIClient(email="test@example.com")

def test_reconstruct_abstract(client):
    inverted_index = {
        "The": [0],
        "quick": [1],
        "brown": [2],
        "fox": [3]
    }
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
        "best_oa_location": {"pdf_url": "http://example.com/test.pdf"}
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
