import pytest
from unittest.mock import Mock
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

def test_update_item_collections_success(client, group_id):
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {'Last-Modified-Version': '43'}
    client.http.session.patch.return_value = mock_response

    # Inputs
    item_key = "ABC12345"
    version = 42
    client.http.last_library_version = version # Set internal state on http client
    new_collections = ["COL1", "COL2"]

    # Action
    result = client.update_item_collections(item_key, version, new_collections)

    # Assertion
    assert result is True
    
    expected_url = f"https://api.zotero.org/groups/{group_id}/items/{item_key}"
    call_args = client.http.session.patch.call_args
    assert call_args[0][0] == expected_url
    
    # Payload should NOT include version (removed to fix 400 Bad Request)
    assert call_args[1]['json'] == {'collections': new_collections}
    
    assert call_args[1]['headers']['If-Unmodified-Since-Version'] == str(version)

def test_update_item_collections_failure(client):
    # Setup mock exception
    client.http.session.patch.side_effect = requests.exceptions.RequestException("API Error")

    # Action
    result = client.update_item_collections("ABC", 1, [])

    # Assertion
    assert result is False