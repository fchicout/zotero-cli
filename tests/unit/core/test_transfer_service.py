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

    new_key = service.transfer_item("K1", source_gw, dest_gw)

    assert new_key == "NEW_K1"
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
        new_key = service.transfer_item("K1", source_gw, dest_gw)

    assert new_key == "NEW_K1"
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

    service.transfer_item("K1", source_gw, dest_gw, delete_source=True)

    source_gw.delete_item.assert_called_once_with("K1", 1)


def test_transfer_item_not_found(service):
    source_gw = MagicMock()
    dest_gw = MagicMock()
    source_gw.get_item.return_value = None

    new_key = service.transfer_item("MISSING", source_gw, dest_gw)
    assert new_key is None
    dest_gw.create_generic_item.assert_not_called()
