from unittest.mock import MagicMock, Mock

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.purge_service import PurgeService
from zotero_cli.core.services.tag_service import TagService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)


@pytest.fixture
def mock_purge_service():
    return MagicMock(spec=PurgeService)


@pytest.fixture
def service(mock_gateway, mock_purge_service):
    return TagService(mock_gateway, mock_purge_service)


def create_item(key, tags):
    return ZoteroItem(key=key, version=1, item_type="journalArticle", tags=tags)


def test_list_tags(service, mock_gateway):
    mock_gateway.get_tags.return_value = ["tag1", "tag2"]
    tags = service.list_tags()
    assert tags == ["tag1", "tag2"]


def test_add_tags_to_item(service, mock_gateway):
    item = create_item("KEY1", ["existing"])
    mock_gateway.update_item_metadata.return_value = True

    result = service.add_tags_to_item("KEY1", item, ["new"])

    assert result is True
    args = mock_gateway.update_item_metadata.call_args
    assert args[0][0] == "KEY1"
    assert args[0][1] == 1
    assert "tags" in args[0][2]

    call_tags = args[0][2]["tags"]
    assert len(call_tags) == 2
    tag_strings = {t["tag"] for t in call_tags}
    assert tag_strings == {"existing", "new"}


def test_remove_tags_from_item(service, mock_gateway):
    item = create_item("KEY1", ["keep", "remove"])
    mock_gateway.update_item_metadata.return_value = True

    result = service.remove_tags_from_item("KEY1", item, ["remove"])

    assert result is True
    args = mock_gateway.update_item_metadata.call_args
    call_tags = args[0][2]["tags"]
    assert len(call_tags) == 1
    assert call_tags[0]["tag"] == "keep"


def test_rename_tag(service, mock_gateway):
    item1 = create_item("KEY1", ["old", "other"])
    item2 = create_item("KEY2", ["old"])
    mock_gateway.get_items_by_tag.return_value = iter([item1, item2])
    mock_gateway.update_item_metadata.return_value = True

    count = service.rename_tag("old", "new")

    assert count == 2
    assert mock_gateway.update_item_metadata.call_count == 2

    # Verify item1 update
    call1 = mock_gateway.update_item_metadata.call_args_list[0]
    tags1 = {t["tag"] for t in call1[0][2]["tags"]}
    assert tags1 == {"new", "other"}


def test_delete_tag(service, mock_gateway, mock_purge_service):
    item1 = create_item("KEY1", ["delete_me", "stay"])
    mock_gateway.get_items_by_tag.return_value = iter([item1])

    mock_purge_service.purge_tags.return_value = {"deleted": 1, "skipped": 0, "errors": 0}

    count = service.delete_tag("delete_me", dry_run=False)

    assert count == 1
    mock_purge_service.purge_tags.assert_called_once_with(["KEY1"], tag_name="delete_me", dry_run=False)
