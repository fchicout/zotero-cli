import os
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.services.transfer_service import TransferService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def service():
    return TransferService()


def test_transfer_item_success(service):
    source_gw = MagicMock()
    dest_gw = MagicMock()

    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="T")
    item.raw_data = {"data": {"title": "T", "key": "K1", "version": 1, "library": "L1"}}
    source_gw.get_item.return_value = item
    source_gw.get_item_children.return_value = []

    dest_gw.create_generic_item.return_value = "NEW_K1"

    result = service.transfer_item("K1", source_gw, dest_gw)

    assert result.new_key == "NEW_K1" and result.complete
    dest_gw.create_generic_item.assert_called_once()
    # Check that key/version/library were stripped
    args = dest_gw.create_generic_item.call_args[0][0]
    assert "key" not in args
    assert "version" not in args
    assert "library" not in args
    assert args["title"] == "T"


def test_transfer_item_with_children(service):
    source_gw = MagicMock()
    dest_gw = MagicMock()

    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="T")
    item.raw_data = {"data": {"title": "T"}}
    source_gw.get_item.return_value = item

    note = {"key": "N1", "data": {"itemType": "note", "note": "Hello"}}
    att = {
        "key": "A1",
        "data": {"itemType": "attachment", "linkMode": "imported_file", "filename": "f.pdf"},
    }
    source_gw.get_item_children.return_value = [note, att]

    dest_gw.create_generic_item.return_value = "NEW_K1"
    source_gw.download_attachment.return_value = True

    # Mock os.path.exists to always return True for the downloaded file in the tmp dir
    with patch("os.path.exists", return_value=True):
        result = service.transfer_item("K1", source_gw, dest_gw)

    assert result.new_key == "NEW_K1" and result.copied_children == 2
    dest_gw.create_note.assert_called_once_with("NEW_K1", "Hello")
    dest_gw.upload_attachment.assert_called_once()


def test_transfer_item_with_delete(service):
    source_gw = MagicMock()
    dest_gw = MagicMock()

    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="T")
    item.raw_data = {"data": {"title": "T"}}
    source_gw.get_item.return_value = item
    source_gw.get_item_children.return_value = []
    dest_gw.create_generic_item.return_value = "NEW_K1"

    result = service.transfer_item("K1", source_gw, dest_gw, delete_source=True)

    source_gw.delete_item.assert_called_once_with("K1", 1)
    assert result.source_deleted


def test_transfer_item_not_found(service):
    source_gw = MagicMock()
    dest_gw = MagicMock()
    source_gw.get_item.return_value = None

    result = service.transfer_item("MISSING", source_gw, dest_gw)
    assert result.new_key is None
    dest_gw.create_generic_item.assert_not_called()


def _item_with_children(children):
    source_gw = MagicMock()
    dest_gw = MagicMock()
    item = ZoteroItem(key="K1", version=4, item_type="journalArticle", title="T")
    item.raw_data = {"data": {"title": "T"}}
    source_gw.get_item.return_value = item
    source_gw.get_item_children.return_value = children
    dest_gw.create_generic_item.return_value = "NEW_K1"
    return source_gw, dest_gw


def _attachment(key, link_mode, filename="paper.pdf"):
    return {
        "key": key,
        "data": {"itemType": "attachment", "linkMode": link_mode, "filename": filename},
    }


@pytest.mark.parametrize(
    "setup",
    ["download_fails", "upload_fails", "note_fails", "linked_file", "linked_url"],
)
def test_source_is_kept_when_any_child_was_not_copied(service, setup):
    """Issue #396: --delete-source used to delete the source after a partial
    copy, losing the files that didn't make it."""
    children = [{"key": "N1", "data": {"itemType": "note", "note": "n"}}]
    if setup in ("download_fails", "upload_fails"):
        children.append(_attachment("A1", "imported_file"))
    elif setup == "linked_file":
        children.append(_attachment("A1", "linked_file"))
    elif setup == "linked_url":
        children.append({"key": "A1", "data": {"itemType": "attachment", "linkMode": "linked_url"}})
    source_gw, dest_gw = _item_with_children(children)
    source_gw.download_attachment.return_value = setup != "download_fails"
    dest_gw.upload_attachment.return_value = setup != "upload_fails"
    dest_gw.create_note.return_value = setup != "note_fails"

    result = service.transfer_item("K1", source_gw, dest_gw, delete_source=True)

    source_gw.delete_item.assert_not_called()
    assert not result.source_deleted
    assert len(result.failures) == 1 and not result.complete


def test_connector_saved_pdfs_are_transferred(service):
    """imported_url (a PDF saved by the Zotero Connector) is a stored file
    too; it used to be skipped silently before the source was deleted."""
    source_gw, dest_gw = _item_with_children([_attachment("A1", "imported_url")])
    source_gw.download_attachment.return_value = True
    dest_gw.upload_attachment.return_value = True

    result = service.transfer_item("K1", source_gw, dest_gw, delete_source=True)

    dest_gw.upload_attachment.assert_called_once()
    source_gw.delete_item.assert_called_once_with("K1", 4)
    assert result.complete and result.source_deleted


def test_attachment_filename_cannot_escape_the_temp_directory(service):
    source_gw, dest_gw = _item_with_children([_attachment("A1", "imported_file", "../../evil.pdf")])
    source_gw.download_attachment.return_value = True
    dest_gw.upload_attachment.return_value = True

    service.transfer_item("K1", source_gw, dest_gw)

    saved_to = source_gw.download_attachment.call_args.args[1]
    assert os.path.basename(saved_to) == "evil.pdf"
    assert ".." not in saved_to
