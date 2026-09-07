from unittest.mock import Mock, mock_open, patch

import pytest

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.zotero_api import ZoteroAPIClient


@pytest.fixture
def client():
    c = ZoteroAPIClient("key", "123", "group")
    c.http = Mock()
    # Ensure http methods raise by default for failure tests,
    # but individual tests will override this.
    return c


def test_get_user_groups_failure(client):
    client.http.get.side_effect = Exception("Boom")
    assert client.get_user_groups("uid") == []


def test_get_all_collections_failure(client):
    client.http.get.side_effect = Exception("Boom")
    assert client.get_all_collections() == []


def test_get_tags_failure(client):
    client.http.get.side_effect = Exception("Boom")
    assert client.get_tags() == []


def test_get_items_by_tag_failure(client):
    client.http.get.side_effect = Exception("Boom")
    # Generator should yield nothing
    assert list(client.get_items_by_tag("t")) == []


def test_get_item_failure(client):
    client.http.get.side_effect = Exception("Boom")
    assert client.get_item("K1") is None


def test_get_item_non_dict_response(client, caplog):
    """Issue #207: a malformed key (e.g. a bare DOI) can route to an
    endpoint that returns a list instead of an item object/404 - this must
    fail with a clear message, not an opaque AttributeError."""
    client.http.get.return_value.json.return_value = []

    with caplog.at_level("ERROR"):
        assert client.get_item("10.1109/TIFS.2024.3376968") is None
    assert "is not a valid Zotero item key" in caplog.text
    assert "'list' object has no attribute" not in caplog.text


def test_get_items_in_collection_failure(client):
    client.http.get.side_effect = Exception("Boom")
    assert list(client.get_items_in_collection("C1")) == []


def test_get_item_children_failure(client):
    client.http.get.side_effect = Exception("Boom")
    assert client.get_item_children("K1") == []


# Write Operations Failures


def test_create_collection_failure(client):
    client.http.post.side_effect = Exception("Boom")
    assert client.create_collection("New") is None


def test_create_item_failure(client):
    p = ResearchPaper(title="T", abstract="A")
    client.http.post.side_effect = Exception("Boom")
    assert client.create_item(p, "C1") is False


def test_create_note_failure(client):
    client.http.post.side_effect = Exception("Boom")
    assert client.create_note("P1", "body") is False


def test_update_note_failure(client):
    client.http.patch.side_effect = Exception("Boom")
    assert client.update_note("K1", 1, "body") is False


def test_delete_item_failure(client):
    client.http.delete.side_effect = Exception("Boom")
    assert client.delete_item("K1", 1) is False


def test_update_item_metadata_failure(client):
    client.http.patch.side_effect = Exception("Boom")
    assert client.update_item_metadata("K1", 1, {}) is False


def test_upload_attachment_failure_post(client):
    # Fail at step 1
    client.http.post.side_effect = Exception("Boom")
    assert client.upload_attachment("P1", "dummy.pdf") is False


@patch("os.path.basename")
@patch("os.path.getmtime")
@patch("os.path.getsize")
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
def test_upload_attachment_failure_auth(mock_file, mock_getsize, mock_mtime, mock_base, client):
    # Pass step 1, fail step 2
    mock_base.return_value = "f.pdf"
    mock_getsize.return_value = 4

    # Step 1 success
    res1 = Mock()
    res1.json.return_value = {"successful": {"0": {"key": "K"}}}

    # Step 2 fail
    client.http.post.return_value = res1
    client.http.post_form.side_effect = Exception("Auth Boom")

    assert client.upload_attachment("P1", "f.pdf") is False

    # Issue #191: a failure after step 1 already created the placeholder
    # attachment item must clean it up, not leave an orphaned empty item.
    client.http.delete.assert_called_once_with("items/K", version_check=True)


@patch("os.path.basename")
@patch("os.path.getmtime")
@patch("os.path.getsize")
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
def test_upload_attachment_step2_headers_omit_if_unmodified_since_version(
    mock_file, mock_getsize, mock_mtime, mock_base, client
):
    """Issue #191 bug 1: Zotero 428s step 2 (upload authorization) if
    If-Unmodified-Since-Version is sent alongside If-None-Match: * - there's
    no prior version of a just-created attachment to be unmodified since."""
    mock_base.return_value = "f.pdf"
    mock_getsize.return_value = 4

    res1 = Mock()
    res1.json.return_value = {"successful": {"0": {"key": "K"}}}
    client.http.post.return_value = res1

    res_auth = Mock()
    res_auth.json.return_value = {"exists": 1}
    client.http.post_form.return_value = res_auth

    client.upload_attachment("P1", "f.pdf")

    auth_call = client.http.post_form.call_args_list[0]
    headers = auth_call.kwargs["headers"]
    assert headers["If-None-Match"] == "*"
    assert "If-Unmodified-Since-Version" not in headers


@patch("os.path.basename")
@patch("os.path.getmtime")
@patch("os.path.getsize")
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
def test_upload_attachment_step4_headers_include_if_none_match(
    mock_file, mock_getsize, mock_mtime, mock_base, client
):
    """Issue #191 bug 2: Zotero 428s step 4 (registering the upload) with
    "If-Match/If-None-Match header not provided" without this."""
    mock_base.return_value = "f.pdf"
    mock_getsize.return_value = 4

    res1 = Mock()
    res1.json.return_value = {"successful": {"0": {"key": "K"}}}
    client.http.post.return_value = res1

    res_auth = Mock()
    res_auth.json.return_value = {
        "exists": 0,
        "url": "http://s3.upload",
        "params": {},
        "uploadKey": "UPLOAD_KEY",
    }
    client.http.post_form.return_value = res_auth

    success = client.upload_attachment("P1", "f.pdf")

    assert success is True
    reg_call = client.http.post_form.call_args_list[1]
    assert reg_call.kwargs["headers"]["If-None-Match"] == "*"


@patch("os.path.basename")
@patch("os.path.getmtime")
@patch("os.path.getsize")
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
def test_upload_attachment_failure_register_cleans_up_orphan(
    mock_file, mock_getsize, mock_mtime, mock_base, client
):
    """Issue #191: a step-4 failure must also clean up the orphaned
    placeholder item, not just a step-2 failure."""
    mock_base.return_value = "f.pdf"
    mock_getsize.return_value = 4

    res1 = Mock()
    res1.json.return_value = {"successful": {"0": {"key": "K"}}}

    res_auth = Mock()
    res_auth.json.return_value = {
        "exists": 0,
        "url": "http://s3.upload",
        "params": {},
        "uploadKey": "UPLOAD_KEY",
    }

    client.http.post.return_value = res1
    client.http.post_form.side_effect = [res_auth, Exception("Register Boom")]

    assert client.upload_attachment("P1", "f.pdf") is False
    client.http.delete.assert_called_once_with("items/K", version_check=True)
