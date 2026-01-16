import pytest
from unittest.mock import Mock, patch, MagicMock
import os
from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)

@pytest.fixture
def mock_aggregator():
    return Mock(spec=MetadataAggregatorService)

@pytest.fixture
def service(mock_gateway, mock_aggregator):
    # Pass mock_gateway for all repo interfaces since it implements them all
    return AttachmentService(mock_gateway, mock_gateway, mock_gateway, mock_gateway, mock_aggregator)

def create_item(key="KEY1", doi="10.1234/test"):
    return ZoteroItem(key=key, version=1, item_type="journalArticle", title="Test Paper", doi=doi)

def test_collection_not_found(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = None
    count = service.attach_pdfs_to_collection("NonExistent")
    assert count == 0
    mock_gateway.get_items_in_collection.assert_not_called()

@patch('zotero_cli.core.services.attachment_service.requests.get')
@patch('zotero_cli.core.services.attachment_service.os.remove')
@patch('zotero_cli.core.services.attachment_service.tempfile.mkstemp')
@patch('zotero_cli.core.services.attachment_service.os.fdopen')
@patch('zotero_cli.core.services.attachment_service.os.path.exists')
def test_attach_pdf_success(mock_exists, mock_fdopen, mock_mkstemp, mock_remove, mock_get, service, mock_gateway, mock_aggregator):
    # Setup mocks
    mock_exists.return_value = True
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = create_item()
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.get_item.return_value = item
    
    # 1. No existing PDF
    mock_gateway.get_item_children.return_value = []
    
    # 2. Metadata found with PDF URL
    metadata = ResearchPaper(title="Test", abstract="", pdf_url="http://example.com/paper.pdf")
    mock_aggregator.get_enriched_metadata.return_value = metadata
    
    # 3. Download setup
    mock_mkstemp.return_value = (123, "/tmp/temp.pdf")
    mock_file = MagicMock()
    mock_fdopen.return_value.__enter__.return_value = mock_file
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [b"pdf-content"]
    mock_get.return_value = mock_response

    # 4. Upload success
    mock_gateway.upload_attachment.return_value = True

    # Run
    count = service.attach_pdfs_to_collection("TestCollection")
    
    # Assertions
    assert count == 1
    mock_gateway.get_collection_id_by_name.assert_called_with("TestCollection")
    mock_gateway.get_item_children.assert_called_with("KEY1")
    mock_aggregator.get_enriched_metadata.assert_called_with("10.1234/test")
    mock_get.assert_called_with("http://example.com/paper.pdf", stream=True, timeout=30)
    mock_gateway.upload_attachment.assert_called_with("KEY1", "/tmp/temp.pdf")
    mock_remove.assert_called_with("/tmp/temp.pdf")

def test_already_has_pdf(service, mock_gateway, mock_aggregator):
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = create_item()
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.get_item.return_value = item
    
    # Simulate existing PDF attachment
    attachment = {
        'data': {
            'itemType': 'attachment',
            'linkMode': 'imported_file',
            'contentType': 'application/pdf'
        }
    }
    mock_gateway.get_item_children.return_value = [attachment]
    
    count = service.attach_pdfs_to_collection("TestCollection")
    
    assert count == 0
    mock_aggregator.get_enriched_metadata.assert_not_called()

def test_no_identifier(service, mock_gateway, mock_aggregator):
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = ZoteroItem(key="KEY1", version=1, item_type="note") # No DOI/ArXiv
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.get_item.return_value = item
    mock_gateway.get_item_children.return_value = []

    count = service.attach_pdfs_to_collection("TestCollection")
    
    assert count == 0
    mock_aggregator.get_enriched_metadata.assert_not_called()

@patch('zotero_cli.core.services.attachment_service.requests.get')
def test_download_failure(mock_get, service, mock_gateway, mock_aggregator):
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = create_item()
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.get_item.return_value = item
    mock_gateway.get_item_children.return_value = []
    
    metadata = ResearchPaper(title="Test", abstract="", pdf_url="http://example.com/fail.pdf")
    mock_aggregator.get_enriched_metadata.return_value = metadata
    
    # Simulate download error
    mock_get.side_effect = Exception("Download failed")

    count = service.attach_pdfs_to_collection("TestCollection")
    
    assert count == 0
    mock_gateway.upload_attachment.assert_not_called()
