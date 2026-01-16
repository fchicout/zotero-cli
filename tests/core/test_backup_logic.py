import json
import pytest
from unittest.mock import Mock, MagicMock, patch
import zipfile
from io import BytesIO

from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_gateway():
    return Mock()

@pytest.fixture
def service(mock_gateway):
    return BackupService(mock_gateway)

def test_backup_creates_valid_zip_structure(service, mock_gateway):
    # Setup
    mock_gateway.get_items_in_collection.return_value = iter([
        ZoteroItem.from_raw_zotero_item({"key": "A", "data": {"title": "Paper 1", "version": 1, "itemType": "journalArticle"}})
    ])
    mock_gateway.get_collection.return_value = {"key": "col_1", "data": {"name": "My Collection"}}
    
    # In-memory output file
    output_buffer = BytesIO()
    
    # Action
    service.backup_collection("col_1", output_buffer)
    
    # Verify
    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        # Check Manifest
        assert "manifest.json" in zf.namelist()
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["scope_type"] == "collection"
        assert manifest["root_collection_name"] == "My Collection"
        
        # Check Data
        assert "data.json" in zf.namelist()
        data = json.loads(zf.read("data.json").decode("utf-8"))
        assert len(data) == 1
        assert data[0]["key"] == "A"
        
        # Verify LZMA usage (We can't easily check compression type on read, 
        # but we can verify strict calls in a separate test if needed. 
        # For now, logical structure is key).

def test_backup_system_export(service, mock_gateway):
    # Setup for full system backup
    mock_gateway.get_all_collections.return_value = []
    mock_gateway.get_items_in_collection.return_value = iter([]) # Assume root has nothing for simplicity
    
    output_buffer = BytesIO()
    service.backup_system(output_buffer)
    
    output_buffer.seek(0)
    with zipfile.ZipFile(output_buffer, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["scope_type"] == "library"
