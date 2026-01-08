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

def test_get_tags_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"tag": "tag1"}, {"tag": "tag2"}]
    client.session.get.return_value = mock_response

    tags = client.get_tags()
    assert tags == ["tag1", "tag2"]

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

def test_get_item_success(client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "K1", "data": {"title": "T1"}, "meta": {}, "version": 1}
    mock_response.headers = {} # Ensure headers.get returns None, not a Mock
    client.session.get.return_value = mock_response

    item = client.get_item("K1")
    assert item is not None
    assert item.key == "K1"

def test_get_item_failure(client):
    client.session.get.side_effect = requests.exceptions.RequestException("404")
    item = client.get_item("K1")
    assert item is None

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

def test_update_item_metadata_failure(client):
    client.session.patch.side_effect = requests.exceptions.RequestException("API Error")
    success = client.update_item_metadata("K1", 1, {"title": "New"})
    assert success is False