import pytest
from unittest.mock import patch, Mock
from zotero_cli.infra.semantic_scholar_api import SemanticScholarAPIClient

@pytest.fixture
def client():
    return SemanticScholarAPIClient()

@patch('requests.get')
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
            {"externalIds": {}} # Ref without DOI
        ]
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

@patch('requests.get')
def test_get_paper_metadata_not_found(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    
    metadata = client.get_paper_metadata("10.0000/missing")
    assert metadata is None