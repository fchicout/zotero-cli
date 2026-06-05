import os
from unittest.mock import MagicMock, patch

import requests

from zotero_cli.infra.unpaywall_api import UnpaywallAPIClient


def test_unpaywall_client_init():
    # 1. Custom email
    client = UnpaywallAPIClient(email="custom@test.com")
    assert client.email == "custom@test.com"

    # 2. Env fallback
    with patch.dict(os.environ, {"UNPAYWALL_EMAIL": "env@test.com"}):
        client2 = UnpaywallAPIClient()
        assert client2.email == "env@test.com"

    # 3. Default fallback
    with patch.dict(os.environ, {}):
        if "UNPAYWALL_EMAIL" in os.environ:
            del os.environ["UNPAYWALL_EMAIL"]
        client3 = UnpaywallAPIClient()
        assert client3.email == "unpaywall_client@zotero_cli.com"


def test_get_paper_metadata_invalid_doi():
    client = UnpaywallAPIClient()
    assert client.get_paper_metadata("not-a-doi") is None


def test_get_paper_metadata_success():
    client = UnpaywallAPIClient(email="test@test.com")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "title": "Unpaywall Paper",
        "doi": "10.1000/xyz123",
        "doi_url": "https://doi.org/10.1000/xyz123",
        "year": 2024,
        "publisher": "Awesome Publisher",
        "z_authors": [
            {"given": "Fábio", "family": "Chicout"},
            {"given": "Jane", "family": "Doe"}
        ],
        "best_oa_location": {
            "url_for_pdf": "https://example.com/best.pdf"
        }
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("10.1000/xyz123")
        assert paper is not None
        assert paper.title == "Unpaywall Paper"
        assert paper.authors == ["Fábio Chicout", "Jane Doe"]
        assert paper.publication == "Awesome Publisher"
        assert paper.pdf_url == "https://example.com/best.pdf"
        assert paper.year == "2024"


def test_get_paper_metadata_journal_name_and_oa_locations_fallback():
    client = UnpaywallAPIClient()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "title": "OA Paper",
        "journal_name": "Journal of Testing",
        "doi": "10.1000/abc",
        "best_oa_location": None,
        "oa_locations": [
            {"url_for_pdf": None},
            {"url_for_pdf": "https://example.com/fallback.pdf"}
        ]
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("10.1000/abc")
        assert paper is not None
        assert paper.publication == "Journal of Testing"
        assert paper.pdf_url == "https://example.com/fallback.pdf"


def test_get_paper_metadata_http_error_404():
    client = UnpaywallAPIClient()
    mock_response = MagicMock()
    mock_response.status_code = 404
    http_err = requests.exceptions.HTTPError(response=mock_response)

    with patch.object(client, "_get", side_effect=http_err):
        assert client.get_paper_metadata("10.1000/err") is None


def test_get_paper_metadata_http_error_generic():
    client = UnpaywallAPIClient()
    mock_response = MagicMock()
    mock_response.status_code = 500
    http_err = requests.exceptions.HTTPError(response=mock_response)

    with patch.object(client, "_get", side_effect=http_err):
        assert client.get_paper_metadata("10.1000/err") is None


def test_get_paper_metadata_generic_exception():
    client = UnpaywallAPIClient()
    with patch.object(client, "_get", side_effect=ValueError("crash")):
        assert client.get_paper_metadata("10.1000/err") is None
