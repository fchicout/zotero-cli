from unittest.mock import Mock, patch

import pytest
import requests

from zotero_cli.infra.crossref_api import CrossRefAPIClient


@pytest.fixture
def client():
    return CrossRefAPIClient()


@patch("requests.Session.get")
def test_get_paper_metadata_success(mock_get, client):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "message": {
            "title": ["Test Paper"],
            "abstract": "Test Abstract",
            "author": [{"given": "John", "family": "Doe"}, {"given": "Jane", "family": "Smith"}],
            "published-print": {"date-parts": [[2023]]},
            "DOI": "10.1000/main.paper",
            "URL": "http://dx.doi.org/10.1000/main.paper",
            "is-referenced-by-count": 42,
            "reference": [
                {"DOI": "10.1000/cited.paper.1"},
                {"unrelated_field": "some_value"},
                {"DOI": "10.1000/cited.paper.2"},
                {"DOI": ""},
            ],
        }
    }
    mock_get.return_value = mock_response

    doi = "10.1000/main.paper"
    metadata = client.get_paper_metadata(doi)

    assert metadata is not None
    assert metadata.title == "Test Paper"
    assert metadata.authors == ["John Doe", "Jane Smith"]
    assert metadata.year == "2023"
    assert metadata.doi == "10.1000/main.paper"
    assert metadata.citation_count == 42
    assert len(metadata.references) == 2
    assert "10.1000/cited.paper.1" in metadata.references
    assert "10.1000/cited.paper.2" in metadata.references


@patch("requests.Session.get")
def test_get_paper_metadata_api_error(mock_get, client):
    mock_get.side_effect = requests.exceptions.RequestException("Network error")
    doi = "10.1000/error.paper"
    metadata = client.get_paper_metadata(doi)
    assert metadata is None
