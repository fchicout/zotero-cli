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
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
def test_upload_attachment_failure_auth(mock_file, mock_mtime, mock_base, client):
    # Pass step 1, fail step 2
    mock_base.return_value = "f.pdf"

    # Step 1 success
    res1 = Mock()
    res1.json.return_value = {"successful": {"0": {"key": "K"}}}

    # Step 2 fail
    client.http.post.return_value = res1
    client.http.post_form.side_effect = Exception("Auth Boom")

    assert client.upload_attachment("P1", "f.pdf") is False
