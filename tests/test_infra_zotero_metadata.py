import pytest
from unittest.mock import Mock
from zotero_cli.infra.zotero_api import ZoteroAPIClient
import requests

@pytest.fixture
def api_key():
    return "test_key"

@pytest.fixture
def group_id():
    return "12345"

@pytest.fixture
def client(api_key, group_id):
    client = ZoteroAPIClient(api_key, group_id)
    client.session = Mock(spec=requests.Session)
    client.session.headers = {}
    return client

def test_update_item_metadata_success(client, group_id):
    mock_response = Mock()
    mock_response.status_code = 204 # No Content
    mock_response.headers = {'Last-Modified-Version': '11'}
    client.session.patch.return_value = mock_response

    item_key = "ITEM123"
    version = 10
    client.last_library_version = version # Set internal state
    metadata = {"abstractNote": "New abstract"}

    result = client.update_item_metadata(item_key, version, metadata)
    
    assert result is True
    
    expected_url = f"https://api.zotero.org/groups/{group_id}/items/{item_key}"
    call_args = client.session.patch.call_args
    assert call_args[0][0] == expected_url
    assert call_args[1]['json'] == metadata
    assert call_args[1]['headers']['If-Unmodified-Since-Version'] == str(version)

def test_update_item_metadata_failure(client):
    client.session.patch.side_effect = requests.exceptions.RequestException("API Error")
    
    result = client.update_item_metadata("ITEM123", 1, {})
    assert result is False