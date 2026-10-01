from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from zotero_cli.core.exceptions import AuthError, NotFound, Unavailable
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.zotero_api import ZoteroAPIClient


@pytest.fixture
def client():
    c = ZoteroAPIClient("key", "123", "group")
    c.http = Mock()
    # Ensure http methods raise by default for failure tests,
    # but individual tests will override this.
    return c


READS: list[tuple[str, tuple[str, ...], object]] = [
    ("get_user_groups", ("uid",), []),
    ("get_all_collections", (), []),
    ("get_tags", (), []),
    ("get_item", ("K1",), None),
    ("get_item_children", ("K1",), []),
]


@pytest.mark.parametrize("method, args, default", READS)
def test_a_missing_object_gives_the_default(client, method, args, default):
    client.http.get.side_effect = NotFound("gone")
    assert getattr(client, method)(*args) == default


@pytest.mark.parametrize(
    "error", [AuthError("key rejected"), Unavailable("down"), Exception("Boom")]
)
@pytest.mark.parametrize("method, args, default", READS)
def test_other_failures_are_not_reported_as_empty(client, method, args, default, error):
    """Issue #369: a rejected key or an outage used to look like "not found"
    or an empty library, with exit status 0."""
    client.http.get.side_effect = error
    with pytest.raises(type(error)):
        getattr(client, method)(*args)


@pytest.mark.parametrize("error", [AuthError("key rejected"), Unavailable("down")])
def test_item_listings_raise_instead_of_truncating(client, error):
    client.http.get.side_effect = error
    with pytest.raises(type(error)):
        list(client.get_items_in_collection("C1"))
    with pytest.raises(type(error)):
        list(client.get_items_by_tag("t"))


def test_get_item_non_dict_response(client, caplog):
    """Issue #207: a malformed key (e.g. a bare DOI) can route to an
    endpoint that returns a list instead of an item object/404 - this must
    fail with a clear message, not an opaque AttributeError."""
    client.http.get.return_value.json.return_value = []

    with caplog.at_level("INFO"):
        assert client.get_item("10.1109/TIFS.2024.3376968") is None
    assert "is not a valid Zotero item key" in caplog.text
    assert "'list' object has no attribute" not in caplog.text


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
    client.get_item = MagicMock(return_value=MagicMock(version=3))
    client.http.delete.return_value = MagicMock(status_code=204)

    assert client.upload_attachment("P1", "f.pdf") is False

    # Issue #191: a failure after step 1 already created the placeholder
    # attachment item must clean it up, not leave an orphaned empty item -
    # deleted at its current version (Issue #384).
    client.http.delete.assert_called_once_with("items/K", version=3)


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

    client.get_item = MagicMock(return_value=MagicMock(version=3))
    client.http.delete.return_value = MagicMock(status_code=204)
    assert client.upload_attachment("P1", "f.pdf") is False
    # The orphaned placeholder is deleted at its current version (Issue #384).
    client.http.delete.assert_called_once_with("items/K", version=3)
