import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    gateway = MagicMock()
    # Mocking interfaces that we added
    gateway.get_all_items.return_value = iter([])
    gateway.get_orphan_items.return_value = iter([])
    gateway.get_item_children.return_value = []
    gateway.download_attachment.return_value = True
    return gateway


@pytest.fixture
def service(mock_gateway):
    return BackupService(mock_gateway)


def test_backup_collection_recursive_attachments(service, mock_gateway):
    # Setup
    parent_item = ZoteroItem.from_raw_zotero_item(
        {
            "key": "PARENT1",
            "version": 1,
            "data": {"title": "Main Paper", "itemType": "journalArticle"},
        }
    )

    child_item_raw = {
        "key": "CHILD1",
        "version": 1,
        "data": {
            "key": "CHILD1",
            "itemType": "attachment",
            "linkMode": "imported_file",
            "filename": "paper.pdf",
            "title": "Attached PDF",
        },
    }
    child_item = ZoteroItem.from_raw_zotero_item(child_item_raw)

    mock_gateway.get_collection.return_value = {"key": "col1", "data": {"name": "Test Col"}}
    mock_gateway.get_items_in_collection.return_value = iter([parent_item])
    mock_gateway.get_item_children.return_value = [{"key": "CHILD1"}]
    mock_gateway.get_item.side_effect = lambda k: child_item if k == "CHILD1" else None

    # Mock successful download
    def mock_download(key, path):
        with open(path, "w") as f:
            f.write("fake pdf content")
        return True

    mock_gateway.download_attachment.side_effect = mock_download

    output_buffer = BytesIO()

    # Action
    service.backup_collection("col1", output_buffer)

    # Verify
    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "data.json" in namelist
        assert "attachments/PARENT1/paper.pdf" in namelist

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        file_entry = manifest["file_map"]["CHILD1"]
        assert file_entry["path"] == "attachments/PARENT1/paper.pdf"
        assert "checksum" in file_entry
        assert len(file_entry["checksum"]) == 64  # SHA-256 length
        content = zf.read("attachments/PARENT1/paper.pdf").decode("utf-8")
        assert content == "fake pdf content"


def test_backup_system_coverage(service, mock_gateway):
    # Setup
    item1 = ZoteroItem.from_raw_zotero_item(
        {"key": "I1", "data": {"title": "T1", "itemType": "book"}}
    )
    item2 = ZoteroItem.from_raw_zotero_item(
        {"key": "I2", "data": {"title": "T2", "itemType": "thesis"}}
    )

    mock_gateway.get_all_items.return_value = iter([item1, item2])
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "Col 1"}},
        {"key": "C2", "data": {"name": "Col 2"}},
    ]

    output_buffer = BytesIO()

    # Action
    service.backup_system(output_buffer)

    # Verify
    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "data.json" in namelist
        assert "collections.json" in namelist

        data = json.loads(zf.read("data.json").decode("utf-8"))
        assert len(data) == 2

        cols = json.loads(zf.read("collections.json").decode("utf-8"))
        assert len(cols) == 2
        assert cols[0]["key"] == "C1"


def test_backup_handles_download_failures(service, mock_gateway):
    # Setup
    item = ZoteroItem.from_raw_zotero_item({"key": "P1", "data": {"itemType": "journalArticle"}})
    att = ZoteroItem.from_raw_zotero_item(
        {
            "key": "A1",
            "data": {"itemType": "attachment", "linkMode": "imported_file", "filename": "miss.pdf"},
        }
    )

    mock_gateway.get_collection.return_value = {"key": "c", "data": {"name": "n"}}
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.get_item_children.return_value = [{"key": "A1"}]
    mock_gateway.get_item.return_value = att
    mock_gateway.download_attachment.return_value = False  # Simulate failure

    output_buffer = BytesIO()
    service.backup_collection("c", output_buffer)

    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "errors.log" in namelist
        errors = zf.read("errors.log").decode("utf-8")
        assert "Failed to download attachment A1" in errors
        assert "attachments/P1/miss.pdf" not in namelist


def test_backup_system_attachment_before_parent(service, mock_gateway):
    # Setup
    # An attachment is yielded BEFORE its parent item in get_all_items()
    child_item = ZoteroItem.from_raw_zotero_item(
        {
            "key": "CHILD_FIRST",
            "version": 1,
            "data": {
                "key": "CHILD_FIRST",
                "itemType": "attachment",
                "linkMode": "imported_file",
                "filename": "first.pdf",
                "title": "First PDF",
                "parentItem": "PARENT_LATER",
            },
        }
    )
    parent_item = ZoteroItem.from_raw_zotero_item(
        {
            "key": "PARENT_LATER",
            "version": 1,
            "data": {"title": "Later Parent Paper", "itemType": "journalArticle"},
        }
    )

    mock_gateway.get_all_items.return_value = iter([child_item, parent_item])
    mock_gateway.get_all_collections.return_value = []
    mock_gateway.get_item_children.return_value = [{"key": "CHILD_FIRST"}]
    mock_gateway.get_item.side_effect = lambda k: child_item if k == "CHILD_FIRST" else None

    # Mock successful download
    def mock_download(key, path):
        with open(path, "w") as f:
            f.write("traversal order edge case")
        return True

    mock_gateway.download_attachment.side_effect = mock_download

    output_buffer = BytesIO()

    # Action
    service.backup_system(output_buffer)

    # Verify
    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "data.json" in namelist
        assert "attachments/PARENT_LATER/first.pdf" in namelist

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        file_entry = manifest["file_map"]["CHILD_FIRST"]
        assert file_entry["path"] == "attachments/PARENT_LATER/first.pdf"
        assert "checksum" in file_entry
        content = zf.read("attachments/PARENT_LATER/first.pdf").decode("utf-8")
        assert content == "traversal order edge case"


def test_backup_collection_not_found(service, mock_gateway):
    mock_gateway.get_collection.return_value = None
    with pytest.raises(ValueError) as excinfo:
        service.backup_collection("NON_EXISTENT", BytesIO())
    assert "Collection NON_EXISTENT not found" in str(excinfo.value)


def test_backup_duplicate_key_skipping(service, mock_gateway):
    item1 = ZoteroItem.from_raw_zotero_item(
        {"key": "DUP1", "data": {"title": "T1", "itemType": "book"}}
    )
    # Yield the same item key twice
    mock_gateway.get_all_items.return_value = iter([item1, item1])
    mock_gateway.get_all_collections.return_value = []

    output_buffer = BytesIO()
    service.backup_system(output_buffer)

    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        data = json.loads(zf.read("data.json").decode("utf-8"))
        # Should only have 1 item in the backed up data list due to key deduplication
        assert len(data) == 1
        assert data[0]["key"] == "DUP1"


def test_backup_on_item_processed_callback(service, mock_gateway):
    item = ZoteroItem.from_raw_zotero_item(
        {"key": "ITEM1", "data": {"title": "T1", "itemType": "book"}}
    )
    mock_gateway.get_all_items.return_value = iter([item])
    mock_gateway.get_all_collections.return_value = []

    callback_called_with = []
    def callback(i):
        callback_called_with.append(i)

    output_buffer = BytesIO()
    service.backup_system(output_buffer, on_item_processed=callback)

    assert len(callback_called_with) == 1
    assert callback_called_with[0].key == "ITEM1"


def test_backup_attachment_already_in_manifest(service, mock_gateway):
    # If the attachment is already in manifest.file_map, we should skip download
    item = ZoteroItem.from_raw_zotero_item(
        {
            "key": "A1",
            "data": {
                "itemType": "attachment",
                "linkMode": "imported_file",
                "filename": "file.pdf",
                "parentItem": "P1",
            },
        }
    )
    mock_gateway.get_all_items.return_value = iter([item])
    mock_gateway.get_all_collections.return_value = []

    # We will subclass/intercept backup_system to inject a pre-populated file_map
    original_write_zip = service._write_zip
    def mock_write_zip(output, manifest, items, on_item_processed):
        manifest["file_map"]["A1"] = {"path": "already/there.pdf", "checksum": "123"}
        return original_write_zip(output, manifest, items, on_item_processed)

    service._write_zip = mock_write_zip
    output_buffer = BytesIO()
    service.backup_system(output_buffer)

    mock_gateway.download_attachment.assert_not_called()


def test_backup_downloader_exception_handling(service, mock_gateway):
    # Succeeded download but let's cause an exception in hashing/writing
    item = ZoteroItem.from_raw_zotero_item(
        {
            "key": "A2",
            "data": {
                "itemType": "attachment",
                "linkMode": "imported_file",
                "filename": "err.pdf",
                "parentItem": "P1",
            },
        }
    )
    mock_gateway.get_all_items.return_value = iter([item])
    mock_gateway.get_all_collections.return_value = []

    # Mock download_attachment to raise an unexpected Exception
    mock_gateway.download_attachment.side_effect = Exception("OS Crash or similar")

    output_buffer = BytesIO()
    service.backup_system(output_buffer)

    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "errors.log" in namelist
        errors = zf.read("errors.log").decode("utf-8")
        assert "Error processing attachment A2" in errors
        assert "OS Crash or similar" in errors


def test_backup_child_fetching_failure_logging(service, mock_gateway):
    # Parent has child but get_item returns None (child not found / deleted)
    item = ZoteroItem.from_raw_zotero_item(
        {"key": "P1", "data": {"title": "Parent", "itemType": "journalArticle"}}
    )
    mock_gateway.get_all_items.return_value = iter([item])
    mock_gateway.get_all_collections.return_value = []
    mock_gateway.get_item_children.return_value = [{"key": "CHILD_MISSING"}]
    mock_gateway.get_item.return_value = None  # Missing child!

    output_buffer = BytesIO()
    service.backup_system(output_buffer)

    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "errors.log" in namelist
        errors = zf.read("errors.log").decode("utf-8")
        assert "Could not fetch child item CHILD_MISSING for parent P1" in errors
