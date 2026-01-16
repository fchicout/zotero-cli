from unittest.mock import Mock, patch

import pytest

from zotero_cli.infra.unpaywall_api import UnpaywallAPIClient


@pytest.fixture
def client():
    return UnpaywallAPIClient()

@patch('requests.Session.get')
def test_get_paper_metadata_success(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "doi": "10.1234/test",
        "doi_url": "https://doi.org/10.1234/test",
        "title": "Open Access Paper",
        "year": 2024,
        "publisher": "Open Publisher",
        "z_authors": [{"given": "Open", "family": "Scientist"}],
        "best_oa_location": {
            "url_for_pdf": "https://example.com/paper.pdf"
        }
    }
    mock_get.return_value = mock_response

    metadata = client.get_paper_metadata("10.1234/test")

    assert metadata is not None
    assert metadata.title == "Open Access Paper"
    assert metadata.doi == "10.1234/test"
    assert metadata.pdf_url == "https://example.com/paper.pdf"
    assert metadata.year == "2024"
    assert metadata.authors == ["Open Scientist"]

@patch('requests.Session.get')
def test_get_paper_metadata_no_oa(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "doi": "10.1234/closed",
        "title": "Closed Paper",
        "best_oa_location": None,
        "oa_locations": []
    }
    mock_get.return_value = mock_response

    metadata = client.get_paper_metadata("10.1234/closed")

    assert metadata is not None
    assert metadata.pdf_url is None

def test_get_paper_metadata_invalid_doi(client):
    metadata = client.get_paper_metadata("not-a-doi")
    assert metadata is None
