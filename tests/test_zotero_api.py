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
    client = ZoteroAPIClient(api_key, group_id)
    # Mock the session object directly
    client.session = Mock(spec=requests.Session)
    client.session.headers = {}
    return client

# --- Collection Methods ---

def test_get_all_collections_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"key": "C1", "data": {"name": "Col 1"}}]
    mock_response.headers = {"Last-Modified-Version": "100"}
    client.session.get.return_value = mock_response

    collections = client.get_all_collections()
    assert len(collections) == 1
    assert collections[0]["key"] == "C1"
    assert client.last_library_version == 100

def test_get_all_collections_failure(client):
    client.session.get.side_effect = requests.exceptions.RequestException("API Error")
    collections = client.get_all_collections()
    assert collections == []

def test_get_collection_id_by_name_found(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"key": "C1", "data": {"name": "Col 1"}}]
    mock_response.headers = {"Last-Modified-Version": "100"}
    client.session.get.return_value = mock_response
    
    col_id = client.get_collection_id_by_name("Col 1")
    assert col_id == "C1"

def test_get_collection_id_by_name_not_found(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"key": "C1", "data": {"name": "Col 1"}}]
    mock_response.headers = {"Last-Modified-Version": "100"}
    client.session.get.return_value = mock_response
    
    col_id = client.get_collection_id_by_name("Nonexistent")
    assert col_id is None

def test_create_collection_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"successful": {"0": {"key": "NEW_COL"}}}
    client.session.post.return_value = mock_response
    
    col_id = client.create_collection("New Col")
    assert col_id == "NEW_COL"

def test_create_collection_failure(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"successful": {}} # Empty successful
    client.session.post.return_value = mock_response
    
    col_id = client.create_collection("New Col")
    assert col_id is None

def test_create_collection_exception(client):
    client.session.post.side_effect = requests.exceptions.RequestException("API Error")
    col_id = client.create_collection("New Col")
    assert col_id is None

# --- Tag Methods ---

def test_get_tags_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"tag": "tag1"}, {"tag": "tag2"}]
    client.session.get.return_value = mock_response

    tags = client.get_tags()
    assert tags == ["tag1", "tag2"]

def test_get_tags_failure(client):
    client.session.get.side_effect = requests.exceptions.RequestException("API Error")
    tags = client.get_tags()
    assert tags == []

# --- Item Fetching Methods ---

def test_get_items_by_tag_pagination(client):
    # Page 1 - return 100 items to trigger next page
    res1 = Mock()
    res1.status_code = 200
    res1.json.return_value = [{"key": f"K{i}", "data": {"title": f"T{i}"}, "meta": {}, "version": 1} for i in range(100)]
    res1.headers = {"Last-Modified-Version": "101"}
    
    # Page 2 (empty)
    res2 = Mock()
    res2.status_code = 200
    res2.json.return_value = []
    res2.headers = {"Last-Modified-Version": "101"}

    client.session.get.side_effect = [res1, res2]

    items = list(client.get_items_by_tag("test-tag"))
    assert len(items) == 100
    assert client.session.get.call_count == 2

def test_get_items_by_tag_failure(client):
    client.session.get.side_effect = requests.exceptions.RequestException("API Error")
    items = list(client.get_items_by_tag("test-tag"))
    assert len(items) == 0

def test_get_items_in_collection_pagination(client):
    # Similar to by_tag pagination
    res1 = Mock()
    res1.status_code = 200
    res1.json.return_value = [{"key": f"K{i}", "data": {"title": f"T{i}"}, "meta": {}, "version": 1} for i in range(100)]
    res1.headers = {"Last-Modified-Version": "101"}
    
    res2 = Mock()
    res2.status_code = 200
    res2.json.return_value = [{"key": "K100", "data": {"title": "T100"}, "meta": {}, "version": 1}]
    res2.headers = {"Last-Modified-Version": "102"}
    
    res3 = Mock() # Should stop here because res2 had < 100 items
    
    client.session.get.side_effect = [res1, res2]
    
    items = list(client.get_items_in_collection("COL_ID"))
    assert len(items) == 101
    assert client.session.get.call_count == 2

def test_get_items_in_collection_failure(client):
    client.session.get.side_effect = requests.exceptions.RequestException("API Error")
    items = list(client.get_items_in_collection("COL_ID"))
    assert len(items) == 0

def test_get_item_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "K1", "data": {"title": "T1"}, "meta": {}, "version": 1}
    mock_response.headers = {} 
    client.session.get.return_value = mock_response

    item = client.get_item("K1")
    assert item is not None
    assert item.key == "K1"

def test_get_item_failure(client):
    client.session.get.side_effect = requests.exceptions.RequestException("404")
    item = client.get_item("K1")
    assert item is None

def test_get_item_children_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"key": "C1", "itemType": "attachment"}]
    mock_response.headers = {"Last-Modified-Version": "100"}
    client.session.get.return_value = mock_response
    
    children = client.get_item_children("K1")
    assert len(children) == 1
    assert children[0]["key"] == "C1"

def test_get_item_children_failure(client):
    client.session.get.side_effect = requests.exceptions.RequestException("Error")
    children = client.get_item_children("K1")
    assert children == []

# --- Item Modification Methods ---

def test_create_item_success(client):
    paper = ResearchPaper(title="Test", abstract="Test Abstract", authors=["A. Smith", "B. Jones"], year="2023", arxiv_id="1234.5678", doi="10.1234/5678", url="http://url")
    
    mock_response = Mock()
    mock_response.status_code = 200
    client.session.post.return_value = mock_response
    
    success = client.create_item(paper, "COL_ID")
    assert success is True
    
    # Verify payload
    args, kwargs = client.session.post.call_args
    payload = kwargs['json'][0]
    assert payload['title'] == "Test"
    assert len(payload['creators']) == 2
    assert payload['creators'][0]['lastName'] == "Smith"
    assert payload['DOI'] == "10.1234/5678"
    assert "arXiv: 1234.5678" in payload['extra']

def test_create_item_failure(client):
    paper = ResearchPaper(title="Test", abstract="Abstract")
    client.session.post.side_effect = requests.exceptions.RequestException("Error")
    success = client.create_item(paper, "COL_ID")
    assert success is False

def test_create_note_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    client.session.post.return_value = mock_response
    
    success = client.create_note("K1", "<div>Note</div>")
    assert success is True

def test_create_note_failure(client):
    client.session.post.side_effect = requests.exceptions.RequestException("Error")
    success = client.create_note("K1", "Note")
    assert success is False

def test_update_item_collections_success(client):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.headers = {"Last-Modified-Version": "10"}
    client.session.patch.return_value = mock_response
    
    success = client.update_item_collections("K1", 5, ["C1", "C2"])
    assert success is True
    assert client.last_library_version == 10

def test_update_item_collections_failure(client):
    client.session.patch.side_effect = requests.exceptions.RequestException("Error")
    success = client.update_item_collections("K1", 5, ["C1"])
    assert success is False

def test_update_item_metadata_success(client):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.headers = {"Last-Modified-Version": "10"}
    client.session.patch.return_value = mock_response
    
    success = client.update_item_metadata("K1", 5, {"title": "New"})
    assert success is True

def test_update_item_metadata_failure(client):
    client.session.patch.side_effect = requests.exceptions.RequestException("API Error")
    success = client.update_item_metadata("K1", 1, {"title": "New"})
    assert success is False

# --- Delete Item (Retry Logic) ---

def test_delete_item_retry_on_412(client):
    res412 = Mock()
    res412.status_code = 412
    res412.headers = {"Last-Modified-Version": "50"}
    
    res204 = Mock()
    res204.status_code = 204
    res204.headers = {"Last-Modified-Version": "51"}
    
    client.session.delete.side_effect = [res412, res204]
    client.last_library_version = 40

    success = client.delete_item("K1", 40)
    assert success is True
    assert client.last_library_version == 51
    assert client.session.delete.call_count == 2

def test_delete_item_failure(client):
    client.session.delete.side_effect = requests.exceptions.RequestException("Error")
    success = client.delete_item("K1", 1)
    assert success is False

# --- Upload Attachment (Complex) ---

@patch("os.path.basename")
@patch("os.path.getmtime")
@patch("builtins.open", new_callable=mock_open, read_data=b"file content")
@patch("zotero_cli.infra.zotero_api.requests.post")
def test_upload_attachment_full_sequence(mock_req_post, mock_file, mock_mtime, mock_basename, client):
    mock_basename.return_value = "test.pdf"
    mock_mtime.return_value = 1000.0
    
    # 1. Create Attachment
    res_create = Mock()
    res_create.status_code = 200
    res_create.json.return_value = {"successful": {"0": {"key": "ATTACH_KEY"}}}
    
    # 2. Authorization
    res_auth = Mock()
    res_auth.status_code = 200
    res_auth.json.return_value = {
        "exists": 0,
        "url": "http://s3.upload",
        "params": {"p1": "v1"},
        "uploadKey": "UPLOAD_KEY"
    }
    
    # 4. Register
    res_reg = Mock()
    res_reg.status_code = 200
    
    client.session.post.side_effect = [res_create, res_auth, res_reg]
    
    # 3. Actual Upload (requests.post)
    res_upload = Mock()
    res_upload.status_code = 200
    mock_req_post.return_value = res_upload

    success = client.upload_attachment("PARENT_KEY", "/path/to/test.pdf")
    
    assert success is True
    assert client.session.post.call_count == 3
    mock_req_post.assert_called_once()

@patch("os.path.basename")
@patch("os.path.getmtime")
@patch("builtins.open", new_callable=mock_open, read_data=b"file content")
def test_upload_attachment_exists(mock_file, mock_mtime, mock_basename, client):
    mock_basename.return_value = "test.pdf"
    mock_mtime.return_value = 1000.0
    
    # 1. Create Attachment
    res_create = Mock()
    res_create.status_code = 200
    res_create.json.return_value = {"successful": {"0": {"key": "ATTACH_KEY"}}}
    
    # 2. Authorization (File Exists)
    res_auth = Mock()
    res_auth.status_code = 200
    res_auth.json.return_value = {"exists": 1}
    
    client.session.post.side_effect = [res_create, res_auth]
    
    success = client.upload_attachment("PARENT_KEY", "/path/to/test.pdf")
    
    assert success is True
    assert client.session.post.call_count == 2 # Stops after auth

@patch("os.path.basename")
@patch("os.path.getmtime")
@patch("builtins.open", new_callable=mock_open, read_data=b"file content")
def test_upload_attachment_create_fail(mock_file, mock_mtime, mock_basename, client):
    mock_basename.return_value = "test.pdf"
    mock_mtime.return_value = 1000.0
    
    # 1. Create Attachment - Fail via API response
    res_create = Mock()
    res_create.status_code = 200
    res_create.json.return_value = {"successful": {}} # Empty
    
    client.session.post.return_value = res_create
    
    success = client.upload_attachment("PARENT_KEY", "/path/to/test.pdf")
    
    assert success is False

def test_upload_attachment_exception(client):
    client.session.post.side_effect = requests.exceptions.RequestException("Network Error")
    success = client.upload_attachment("PARENT_KEY", "/path/to/test.pdf")
    assert success is False