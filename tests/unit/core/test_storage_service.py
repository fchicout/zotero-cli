from pathlib import Path
from unittest.mock import Mock

import pytest

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.services.storage_service import StorageService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock()


@pytest.fixture
def storage_service(tmp_path, mock_gateway):
    config = ZoteroConfig(
        api_key="key", library_id="123", storage_path=str(tmp_path / "zotero_storage")
    )
    return StorageService(config, mock_gateway)


def test_checkout_items_no_path(mock_gateway):
    config = ZoteroConfig(api_key="key", library_id="123", storage_path=None)
    service = StorageService(config, mock_gateway)
    assert service.checkout_items() == 0


def test_checkout_single_item_success(storage_service, mock_gateway):
    # Setup
    item = ZoteroItem(
        key="ITEM123",
        version=1,
        item_type="attachment",
        raw_data={
            "data": {
                "linkMode": "imported_file",
                "filename": "test_paper.pdf",
                "contentType": "application/pdf",
            }
        },
    )

    # Mocks
    mock_gateway.download_attachment.return_value = True
    mock_gateway.update_attachment_link.return_value = True

    # Execute
    storage_root = Path(storage_service.config.storage_path)
    storage_root.mkdir(parents=True, exist_ok=True)  # Ensure root exists

    success = storage_service.checkout_single_item(item, storage_root)

    # Assert
    assert success is True
    mock_gateway.download_attachment.assert_called_once()
    mock_gateway.update_attachment_link.assert_called_once()

    # Verify path passed to update
    args, _ = mock_gateway.update_attachment_link.call_args
    assert args[0] == "ITEM123"
    assert "test_paper.pdf" in args[2]


def test_checkout_single_item_skip_if_linked(storage_service):
    item = ZoteroItem(
        key="ITEM123",
        version=1,
        item_type="attachment",
        raw_data={
            "data": {
                "linkMode": "linked_file",  # Already linked
                "filename": "test.pdf",
            }
        },
    )
    success = storage_service.checkout_single_item(item, Path("/tmp"))
    assert success is False


def test_checkout_items_integration_flow(storage_service, mock_gateway):
    # Mock Search
    item1 = ZoteroItem(
        key="A",
        version=1,
        item_type="attachment",
        raw_data={"data": {"linkMode": "imported_file", "filename": "a.pdf"}},
    )
    item2 = ZoteroItem(
        key="B",
        version=1,
        item_type="attachment",
        raw_data={"data": {"linkMode": "imported_file", "filename": "b.pdf"}},
    )

    mock_gateway.search_items.return_value = iter([item1, item2])
    mock_gateway.download_attachment.return_value = True
    mock_gateway.update_attachment_link.return_value = True

    count = storage_service.checkout_items(limit=10)

    assert count == 2
    assert mock_gateway.download_attachment.call_count == 2
    assert mock_gateway.update_attachment_link.call_count == 2
