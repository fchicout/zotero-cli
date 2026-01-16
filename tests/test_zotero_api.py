import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
import requests
import os
from zotero_cli.infra.zotero_api import ZoteroAPIClient
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def api_key():
    return "test_api_key"

@pytest.fixture
def group_id():
    return "1234567"

@pytest.fixture
def client(api_key, group_id):
    # Default is group mode
    client = ZoteroAPIClient(api_key, group_id, 'group')
    # Mock the http session
    client.http.session = Mock(spec=requests.Session)
    client.http.session.headers = {}
    return client

def test_init_group_mode(api_key, group_id):
    c = ZoteroAPIClient(api_key, group_id, 'group')
    assert c.http.api_prefix == f"https://api.zotero.org/groups/{group_id}"

def test_init_user_mode(api_key):
    user_id = "999"
    c = ZoteroAPIClient(api_key, user_id, 'user')
    assert c.http.api_prefix == f"https://api.zotero.org/users/{user_id}"

def test_get_user_groups(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"id": 1, "data": {"name": "G1"}}]
    mock_response.headers = {}
    client.http.session.get.return_value = mock_response
    
    groups = client.get_user_groups("123")
    assert len(groups) == 1
    assert groups[0]['data']['name'] == "G1"
    # HttpClient handles prefix, but here we override
    client.http.session.get.assert_called_with("https://api.zotero.org/users/123/groups", params=None)

# --- Collection Methods ---

def test_get_all_collections_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"key": "C1", "data": {"name": "Col 1"}}]
    mock_response.headers = {"Last-Modified-Version": "100"}
    client.http.session.get.return_value = mock_response

    collections = client.get_all_collections()
    assert len(collections) == 1
    assert collections[0]["key"] == "C1"
    # assert client.http.last_library_version == 100 # Not testing http client internals here, but result

def test_get_all_collections_failure(client):
    client.http.session.get.side_effect = requests.exceptions.RequestException("API Error")
    collections = client.get_all_collections()
    assert collections == []

# --- Item Fetching Methods ---

def test_get_items_by_tag_pagination(client):
    res1 = Mock()
    res1.status_code = 200
    res1.json.return_value = [{"key": f"K{i}", "data": {"title": f"T{i}"}, "meta": {}, "version": 1} for i in range(100)]
    res1.headers = {"Last-Modified-Version": "101"}
    
    res2 = Mock()
    res2.status_code = 200
    res2.json.return_value = []
    res2.headers = {"Last-Modified-Version": "101"}

    client.http.session.get.side_effect = [res1, res2]

    items = list(client.get_items_by_tag("test-tag"))
    assert len(items) == 100
    assert client.http.session.get.call_count == 2

def test_get_item_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "K1", "data": {"title": "T1"}, "meta": {}, "version": 1}
    mock_response.headers = {}
    client.http.session.get.return_value = mock_response

    item = client.get_item("K1")
    assert item is not None
    assert item.key == "K1"

def test_get_items_in_collection_top_only(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"key": "K1", "data": {"title": "Top Item"}, "meta": {}, "version": 1}]
    mock_response.headers = {}
    client.http.session.get.return_value = mock_response

    items = list(client.get_items_in_collection("C1", top_only=True))
    assert len(items) == 1
    
    # Verify correct endpoint
    args, kwargs = client.http.session.get.call_args
    assert "/collections/C1/items/top" in args[0]

# --- Item Modification Methods ---

def test_create_item_success(client):
    paper = ResearchPaper(title="Test", abstract="Test Abstract", authors=["A. Smith"], year="2023", arxiv_id="1", doi="10/1", url="u")
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"successful": {"0": {"key": "K1"}}}
    mock_response.headers = {}
    client.http.session.post.return_value = mock_response
    
    success = client.create_item(paper, "COL_ID")
    assert success is True
    
    # Verify payload
    args, kwargs = client.http.session.post.call_args
    payload = kwargs['json'][0]
    assert payload['title'] == "Test"

def test_create_note_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"successful": {"0": {"key": "N1"}}}
    mock_response.headers = {}
    client.http.session.post.return_value = mock_response
    
    success = client.create_note("K1", "<div>Note</div>")
    assert success is True

def test_update_item_collections_success(client):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.headers = {}
    client.http.session.patch.return_value = mock_response
    
    success = client.update_item_collections("K1", 5, ["C1", "C2"])
    assert success is True

# --- Delete Item (Retry Logic handled by Http Client but tested via API Client) ---

def test_delete_item_retry_on_412(client):
    res412 = Mock()
    res412.status_code = 412
    res412.headers = {"Last-Modified-Version": "50"}
    
    res204 = Mock()
    res204.status_code = 204
    res204.headers = {"Last-Modified-Version": "51"}
    
    client.http.session.delete.side_effect = [res412, res204]

    success = client.delete_item("K1", 40)
    assert success is True
    assert client.http.session.delete.call_count == 2

# --- Upload Attachment (Complex) ---

@patch("os.path.basename")
@patch("os.path.getmtime")
@patch("builtins.open", new_callable=mock_open, read_data=b"file content")
@patch("zotero_cli.infra.http_client.requests.post") # Patch the requests used in upload_file
def test_upload_attachment_full_sequence(mock_req_post, mock_file, mock_mtime, mock_basename, client):
    mock_basename.return_value = "test.pdf"
    mock_mtime.return_value = 1000.0
    
    # 1. Create Attachment
    res_create = Mock()
    res_create.status_code = 200
    res_create.json.return_value = {"successful": {"0": {"key": "ATTACH_KEY"}}}
    res_create.headers = {}
    
    # 2. Authorization
    res_auth = Mock()
    res_auth.status_code = 200
    res_auth.json.return_value = {
        "exists": 0,
        "url": "http://s3.upload",
        "params": {"p1": "v1"},
        "uploadKey": "UPLOAD_KEY"
    }
    res_auth.headers = {}
    
    # 4. Register
    res_reg = Mock()
    res_reg.status_code = 200
    res_reg.headers = {}
    
    # Session calls: POST (create), POST (auth), POST (register)
    client.http.session.post.side_effect = [res_create, res_auth, res_reg]
    
    # 3. Actual Upload (requests.post via http.upload_file)
    res_upload = Mock()
    res_upload.status_code = 200
    mock_req_post.return_value = res_upload

    success = client.upload_attachment("PARENT_KEY", "/path/to/test.pdf")
    
    assert success is True
    assert client.http.session.post.call_count == 3
    mock_req_post.assert_called_once()

# --- Generic CRUD Tests ---

def test_create_generic_item(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"successful": {"0": {"key": "GEN_KEY"}}}
    mock_response.headers = {}
    client.http.session.post.return_value = mock_response
    
    key = client.create_generic_item({"itemType": "book", "title": "My Book"})
    assert key == "GEN_KEY"
    args, kwargs = client.http.session.post.call_args
    assert kwargs['json'][0]['itemType'] == "book"

def test_update_item(client):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.headers = {}
    client.http.session.patch.return_value = mock_response
    client.http.last_library_version = 1 # Set version for header check
    
    success = client.update_item("K1", 1, {"title": "New Title"})
    assert success is True
    # Verify session call
    args, kwargs = client.http.session.patch.call_args
    # The URL will be full prefix + endpoint
    assert "items/K1" in args[0]
    assert kwargs['json'] == {"title": "New Title"}
    assert kwargs['headers']['If-Unmodified-Since-Version'] == '1'

def test_get_collection_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "C1", "data": {"name": "Col 1"}}
    mock_response.headers = {}
    client.http.session.get.return_value = mock_response

    col = client.get_collection("C1")
    assert col['key'] == "C1"
    assert "/collections/C1" in client.http.session.get.call_args[0][0]

def test_delete_collection_success(client):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.headers = {}
    client.http.session.delete.return_value = mock_response
    
    success = client.delete_collection("C1", 1)
    assert success is True
    assert "/collections/C1" in client.http.session.delete.call_args[0][0]

def test_rename_collection_success(client):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.headers = {}
    client.http.session.patch.return_value = mock_response
    
    success = client.rename_collection("C1", 1, "New Name")
    assert success is True
    # Verify payload
    args, kwargs = client.http.session.patch.call_args
    assert kwargs['json']['name'] == "New Name"

# --- New Read Methods ---

def test_get_top_collections(client):
    client.http.session.get.return_value.json.return_value = [{"key": "TOP"}]
    client.http.session.get.return_value.status_code = 200
    client.http.session.get.return_value.headers = {}
    cols = client.get_top_collections()
    assert cols[0]['key'] == "TOP"
    assert "/collections/top" in client.http.session.get.call_args[0][0]

def test_get_subcollections(client):
    client.http.session.get.return_value.json.return_value = [{"key": "SUB"}]
    client.http.session.get.return_value.status_code = 200
    client.http.session.get.return_value.headers = {}
    cols = client.get_subcollections("PARENT")
    assert cols[0]['key'] == "SUB"
    assert "/collections/PARENT/collections" in client.http.session.get.call_args[0][0]

def test_get_saved_searches(client):
    client.http.session.get.return_value.json.return_value = [{"key": "SEARCH"}]
    client.http.session.get.return_value.status_code = 200
    client.http.session.get.return_value.headers = {}
    searches = client.get_saved_searches()
    assert searches[0]['key'] == "SEARCH"
    assert "searches" in client.http.session.get.call_args[0][0]

def test_get_trash_items(client):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"key": "TRASH1", "data": {}, "meta": {}, "version": 1}]
    mock_resp.headers = {"Last-Modified-Version": "1"}
    client.http.session.get.return_value = mock_resp
    
    items = list(client.get_trash_items())
    assert len(items) == 1
    assert items[0].key == "TRASH1"
    assert "items/trash" in client.http.session.get.call_args[0][0]