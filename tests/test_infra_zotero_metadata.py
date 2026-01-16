from unittest.mock import Mock

import pytest
import requests

from zotero_cli.infra.zotero_api import ZoteroAPIClient


@pytest.fixture
def api_key():
    return "test_key"

@pytest.fixture
def group_id():
    return "12345"

@pytest.fixture
def client(api_key, group_id):
    client = ZoteroAPIClient(api_key, group_id)
    # Mock http session
    client.http.session = Mock(spec=requests.Session)
    client.http.session.headers = {}
    return client

def test_update_item_metadata_success(client, group_id):
    mock_response = Mock()
    mock_response.status_code = 204 # No Content
    mock_response.headers = {'Last-Modified-Version': '11'}
    client.http.session.patch.return_value = mock_response

    item_key = "ITEM123"
    version = 10
    client.http.last_library_version = version # Set internal state on http client
    metadata = {"abstractNote": "New abstract"}

    result = client.update_item_metadata(item_key, version, metadata)

    assert result is True

    # Http client adds prefix
    expected_url = f"https://api.zotero.org/groups/{group_id}/items/{item_key}"
    call_args = client.http.session.patch.call_args
    assert call_args[0][0] == expected_url
    assert call_args[1]['json'] == metadata
    # Headers are handled in http client, verify they were passed
    # In new http_client.patch, if version_check=True, we add the header.
    # update_item_metadata calls patch(..., version_check=True)
    # So header should be present in the session call.
    assert call_args[1]['headers']['If-Unmodified-Since-Version'] == str(version)

def test_update_item_metadata_failure(client):
    client.http.session.patch.side_effect = requests.exceptions.RequestException("API Error")

    result = client.update_item_metadata("ITEM123", 1, {})
    assert result is False
