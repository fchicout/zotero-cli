from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.services.storage_service import StorageService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock(spec=ZoteroConfig)
    config.storage_path = str(tmp_path / "storage")
    return config


def test_checkout_items_no_path(mock_gateway):
    config = MagicMock(spec=ZoteroConfig)
    config.storage_path = None
    service = StorageService(config, mock_gateway)
    assert service.checkout_items() == 0


def test_mkdir_failure(mock_gateway, tmp_path):
    config = MagicMock(spec=ZoteroConfig)
    # Use a path that can't be created (e.g. child of a file)
    file_path = tmp_path / "somefile"
    file_path.write_text("content")
    config.storage_path = str(file_path / "subdir")

    service = StorageService(config, mock_gateway)
    assert service.checkout_items() == 0


def test_checkout_limit(mock_config, mock_gateway):
    service = StorageService(mock_config, mock_gateway)

    item = ZoteroItem(key="K1", version=1, item_type="attachment")
    item.raw_data = {"data": {"linkMode": "imported_file", "filename": "f1.pdf"}}

    mock_gateway.search_items.return_value = [item] * 5
    mock_gateway.download_attachment.return_value = True
    mock_gateway.update_attachment_link.return_value = True

    # Limit to 2
    count = service.checkout_items(limit=2)
    assert count == 2


def test_checkout_single_item_not_attachment(mock_config, mock_gateway):
    service = StorageService(mock_config, mock_gateway)
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle")
    assert service.checkout_single_item(item, Path(mock_config.storage_path)) is False


def test_checkout_single_item_no_filename_sanitization(mock_config, mock_gateway):
    storage_root = Path(mock_config.storage_path)
    storage_root.mkdir()
    service = StorageService(mock_config, mock_gateway)

    item = ZoteroItem(key="K1", version=1, item_type="attachment")
    item.title = "A Great Paper: Title/Sub"
    item.raw_data = {"data": {"linkMode": "imported_file"}}  # No filename

    def download_sim(key, path):
        Path(path).write_text("pdf")
        return True

    mock_gateway.download_attachment.side_effect = download_sim
    mock_gateway.update_attachment_link.return_value = True

    assert service.checkout_single_item(item, storage_root) is True
    # Should have created sanitized filename: K1_A Great Paper TitleSub.pdf
    expected = storage_root / "K1_A Great Paper TitleSub.pdf"
    assert expected.exists()


def test_checkout_filename_conflict(mock_config, mock_gateway):
    storage_root = Path(mock_config.storage_path)
    storage_root.mkdir()
    service = StorageService(mock_config, mock_gateway)

    filename = "test.pdf"
    (storage_root / filename).write_text("existing")

    item = ZoteroItem(key="K1", version=1, item_type="attachment")
    item.raw_data = {"data": {"linkMode": "imported_file", "filename": filename}}

    def download_sim(key, path):
        Path(path).write_text("pdf")
        return True

    mock_gateway.download_attachment.side_effect = download_sim
    mock_gateway.update_attachment_link.return_value = True

    assert service.checkout_single_item(item, storage_root) is True
    # Should have appended key: K1_test.pdf
    assert (storage_root / "K1_test.pdf").exists()


def test_download_failure_cleanup(mock_config, mock_gateway):
    """Verifies that the service cleans up on False return."""
    storage_root = Path(mock_config.storage_path)
    storage_root.mkdir()
    service = StorageService(mock_config, mock_gateway)

    item = ZoteroItem(key="K1", version=1, item_type="attachment")
    item.raw_data = {"data": {"linkMode": "imported_file", "filename": "fail.pdf"}}

    def download_sim(key, path):
        Path(path).write_text("partial")
        return False

    mock_gateway.download_attachment.side_effect = download_sim

    assert service.checkout_single_item(item, storage_root) is False
    assert not (storage_root / "fail.pdf").exists()


def test_download_exception_cleanup(mock_config, mock_gateway):
    storage_root = Path(mock_config.storage_path)
    storage_root.mkdir()
    service = StorageService(mock_config, mock_gateway)

    item = ZoteroItem(key="K1", version=1, item_type="attachment")
    item.raw_data = {"data": {"linkMode": "imported_file", "filename": "exc.pdf"}}

    mock_gateway.download_attachment.side_effect = RuntimeError("Network down")

    assert service.checkout_single_item(item, storage_root) is False
    assert not (storage_root / "exc.pdf").exists()


def test_update_failure_rollback(mock_config, mock_gateway):
    storage_root = Path(mock_config.storage_path)
    storage_root.mkdir()
    service = StorageService(mock_config, mock_gateway)

    item = ZoteroItem(key="K1", version=1, item_type="attachment")
    item.raw_data = {"data": {"linkMode": "imported_file", "filename": "rollback.pdf"}}

    mock_gateway.download_attachment.return_value = True
    mock_gateway.update_attachment_link.return_value = False

    # download_attachment mock should simulate creating the file
    def download_sim(key, path):
        Path(path).write_text("full pdf")
        return True

    mock_gateway.download_attachment.side_effect = download_sim

    assert service.checkout_single_item(item, storage_root) is False
    assert not (storage_root / "rollback.pdf").exists()  # Should be unlinked


def test_update_exception_rollback(mock_config, mock_gateway):
    storage_root = Path(mock_config.storage_path)
    storage_root.mkdir()
    service = StorageService(mock_config, mock_gateway)

    item = ZoteroItem(key="K1", version=1, item_type="attachment")
    item.raw_data = {"data": {"linkMode": "imported_file", "filename": "exc_rollback.pdf"}}

    def download_sim(key, path):
        Path(path).write_text("full pdf")
        return True

    mock_gateway.download_attachment.side_effect = download_sim
    mock_gateway.update_attachment_link.side_effect = RuntimeError("Zotero API Error")

    assert service.checkout_single_item(item, storage_root) is False
    assert not (storage_root / "exc_rollback.pdf").exists()
