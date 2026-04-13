import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

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
            "title": "Attached PDF"
        }
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
        assert manifest["file_map"]["CHILD1"] == "attachments/PARENT1/paper.pdf"
        
        content = zf.read("attachments/PARENT1/paper.pdf").decode("utf-8")
        assert content == "fake pdf content"


def test_backup_system_coverage(service, mock_gateway):
    # Setup
    item1 = ZoteroItem.from_raw_zotero_item({"key": "I1", "data": {"title": "T1", "itemType": "book"}})
    item2 = ZoteroItem.from_raw_zotero_item({"key": "I2", "data": {"title": "T2", "itemType": "thesis"}})
    
    mock_gateway.get_all_items.return_value = iter([item1, item2])
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "Col 1"}},
        {"key": "C2", "data": {"name": "Col 2"}}
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
    att = ZoteroItem.from_raw_zotero_item({
        "key": "A1", 
        "data": {"itemType": "attachment", "linkMode": "imported_file", "filename": "miss.pdf"}
    })
    
    mock_gateway.get_collection.return_value = {"key": "c", "data": {"name": "n"}}
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.get_item_children.return_value = [{"key": "A1"}]
    mock_gateway.get_item.return_value = att
    mock_gateway.download_attachment.return_value = False # Simulate failure

    output_buffer = BytesIO()
    service.backup_collection("c", output_buffer)

    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "errors.log" in namelist
        errors = zf.read("errors.log").decode("utf-8")
        assert "Failed to download attachment A1" in errors
        assert "attachments/P1/miss.pdf" not in namelist
