from unittest.mock import MagicMock

import pytest

from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.repositories import (
    ZoteroAttachmentRepository,
    ZoteroCollectionRepository,
    ZoteroItemRepository,
    ZoteroNoteRepository,
    ZoteroTagRepository,
)


@pytest.fixture
def mock_gateway():
    return MagicMock()


def test_item_repository_get_item(mock_gateway):
    repo = ZoteroItemRepository(mock_gateway)
    repo.get_item("KEY1")
    mock_gateway.get_item.assert_called_once_with("KEY1")


def test_collection_repository_get_items(mock_gateway):
    repo = ZoteroCollectionRepository(mock_gateway)
    repo.get_items_in_collection("COL1", top_only=True)
    mock_gateway.get_items_in_collection.assert_called_once_with("COL1", True)


def test_tag_repository_add_tags(mock_gateway):
    repo = ZoteroTagRepository(mock_gateway)

    # Mock get_item to return a ZoteroItem with a version
    mock_item = MagicMock(spec=ZoteroItem)
    mock_item.version = 10
    mock_gateway.get_item.return_value = mock_item
    mock_gateway.get_tags_for_item.return_value = ["old_tag"]

    repo.add_tags("KEY1", ["new_tag"])

    mock_gateway.update_item.assert_called_once()
    args = mock_gateway.update_item.call_args[0]
    assert args[0] == "KEY1"
    assert args[1] == 10
    assert "tags" in args[2]


def test_note_repository_create_note(mock_gateway):
    repo = ZoteroNoteRepository(mock_gateway)
    repo.create_note("PARENT", "content")
    mock_gateway.create_note.assert_called_once_with("PARENT", "content")


def test_attachment_repository_upload(mock_gateway):
    repo = ZoteroAttachmentRepository(mock_gateway)
    repo.upload_attachment("PARENT", "file.pdf")
    mock_gateway.upload_attachment.assert_called_once_with("PARENT", "file.pdf", "application/pdf")
