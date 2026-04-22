from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.infra.hal_api import HALAPIClient


@pytest.fixture
def client():
    return HALAPIClient()

def test_map_to_research_paper(client):
    item = {
        "title_s": ["The French Revolution", "La Révolution Française"],
        "abstract_s": ["History of 1789.", "Histoire de 1789."],
        "authFullName_s": ["Robespierre, Maximilien", "Danton, Georges"],
        "journalTitle_s": "Journal of History",
        "producedDateY_i": 2021,
        "doi_s": ["10.1000/hal123"],
        "uri_s": "https://hal.archives-ouvertes.fr/hal-01234567",
        "files_s": ["https://hal.archives-ouvertes.fr/hal-01234567/file/paper.pdf"]
    }
    paper = client._map_to_research_paper(item)
    assert paper.title == "The French Revolution"
    assert paper.abstract == "History of 1789."
    assert paper.authors == ["Robespierre, Maximilien", "Danton, Georges"]
    assert paper.publication == "Journal of History"
    assert paper.year == "2021"
    assert paper.doi == "10.1000/hal123"
    assert paper.url == "https://hal.archives-ouvertes.fr/hal-01234567"
    assert paper.pdf_url == "https://hal.archives-ouvertes.fr/hal-01234567/file/paper.pdf"

def test_get_paper_metadata_hal_id(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": {
            "docs": [{"title_s": ["Paper by HAL ID"], "identifiant_s": "hal-1"}]
        }
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("hal-1")
        assert paper.title == "Paper by HAL ID"
        args, kwargs = client._get.call_args
        assert "identifiant_s:hal-1" in kwargs["params"]["q"]

def test_get_paper_metadata_doi(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": {
            "docs": [{"title_s": ["Paper by DOI"], "doi_s": ["10.1/1"]}]
        }
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("10.1/1")
        assert paper.title == "Paper by DOI"
        args, kwargs = client._get.call_args
        assert "doi_s:10.1/1" in kwargs["params"]["q"]

def test_get_paper_metadata_not_found(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": {"docs": []}}

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("none")
        assert paper is None
