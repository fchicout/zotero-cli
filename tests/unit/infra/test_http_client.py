from unittest.mock import MagicMock, patch

import pytest
import requests

from zotero_cli.infra.http_client import ZoteroHttpClient


def test_resolve_key_identity_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "userID": 12345,
        "username": "myusername",
        "access": {"user": {"library": True}},
    }
    mock_response.raise_for_status.return_value = None

    with patch("zotero_cli.infra.http_client.requests.get", return_value=mock_response) as mock_get:
        data = ZoteroHttpClient.resolve_key_identity("some_api_key")

    assert data["userID"] == 12345
    assert data["username"] == "myusername"

    called_url = mock_get.call_args.args[0]
    assert called_url == f"{ZoteroHttpClient.BASE_URL}/keys/some_api_key"
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["Zotero-API-Key"] == "some_api_key"


def test_resolve_key_identity_invalid_key_raises():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    mock_response.status_code = 403

    with patch("zotero_cli.infra.http_client.requests.get", return_value=mock_response):
        with pytest.raises(requests.exceptions.HTTPError):
            ZoteroHttpClient.resolve_key_identity("bad_key")


def test_resolve_key_identity_does_not_require_library_id():
    """The whole point (Issue #178): no ZoteroHttpClient instance/library_id needed."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"userID": 1, "username": "u", "access": {}}
    mock_response.raise_for_status.return_value = None

    with patch("zotero_cli.infra.http_client.requests.get", return_value=mock_response):
        ZoteroHttpClient.resolve_key_identity("any_key")  # no instance constructed at all
