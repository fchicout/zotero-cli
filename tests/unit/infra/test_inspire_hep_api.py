from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.infra.inspire_hep_api import InspireHEPAPIClient


@pytest.fixture
def client():
    return InspireHEPAPIClient()

def test_map_to_research_paper(client):
    metadata = {
        "titles": [{"title": "HEP Discoveries"}],
        "abstracts": [{"value": "We found a new particle."}],
        "authors": [{"full_name": "Higgs, Peter"}, {"full_name": "Englert, Francois"}],
        "publication_info": [{"journal_title": "Physics Letters B", "year": 2012}],
        "dois": [{"value": "10.1016/j.physletb.2012.08.020"}],
        "arxiv_eprints": [{"value": "1207.7214"}],
        "control_number": 1124337,
        "collaborations": [{"value": "ATLAS"}, {"value": "CMS"}],
        "report_numbers": [{"value": "CERN-PH-EP-2012-218"}]
    }
    paper = client._map_to_research_paper(metadata)
    assert paper.title == "HEP Discoveries"
    assert paper.abstract == "We found a new particle."
    assert paper.authors == ["Higgs, Peter", "Englert, Francois"]
    assert paper.publication == "Physics Letters B"
    assert paper.year == "2012"
    assert paper.doi == "10.1016/j.physletb.2012.08.020"
    assert paper.arxiv_id == "1207.7214"
    assert "Collaborations: ATLAS, CMS" in paper.extra
    assert "Report Numbers: CERN-PH-EP-2012-218" in paper.extra
    assert paper.url == "https://inspirehep.net/literature/1124337"

def test_get_paper_metadata_doi(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "hits": {
            "hits": [{"metadata": {"titles": [{"title": "DOI Paper"}], "control_number": 1}}]
        }
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("10.1/1")
        assert paper.title == "DOI Paper"
        args, kwargs = client._get.call_args
        assert "doi 10.1/1" == kwargs["params"]["q"]

def test_get_paper_metadata_arxiv(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "hits": {"hits": [{"metadata": {"titles": [{"title": "arXiv Paper"}]}}]}
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("1207.7214")
        assert paper.title == "arXiv Paper"
        args, kwargs = client._get.call_args
        assert "eprint 1207.7214" == kwargs["params"]["q"]

def test_get_paper_metadata_recid(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "hits": {"hits": [{"metadata": {"titles": [{"title": "Recid Paper"}]}}]}
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("1124337")
        assert paper.title == "Recid Paper"
        args, kwargs = client._get.call_args
        assert "recid 1124337" == kwargs["params"]["q"]

def test_get_paper_metadata_not_found(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"hits": {"hits": []}}

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("none")
        assert paper is None
