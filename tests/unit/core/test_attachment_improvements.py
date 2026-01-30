from unittest.mock import MagicMock, Mock, patch
import pytest
import os
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)

@pytest.fixture
def mock_aggregator():
    return Mock(spec=MetadataAggregatorService)

@pytest.fixture
def service(mock_gateway, mock_aggregator):
    return AttachmentService(
        mock_gateway, mock_gateway, mock_gateway, mock_gateway, mock_aggregator
    )

def test_looks_like_pdf(service):
    assert service._looks_like_pdf("http://example.com/paper.pdf") is True
    assert service._looks_like_pdf("http://example.com/pdf/12345") is True
    assert service._looks_like_pdf("https://arxiv.org/pdf/2101.00001") is True
    assert service._looks_like_pdf("http://example.com/paper.html") is False
    assert service._looks_like_pdf("") is False

@patch("zotero_cli.core.services.attachment_service.requests.get")
@patch("zotero_cli.core.services.attachment_service.tempfile.mkstemp")
@patch("zotero_cli.core.services.attachment_service.os.fdopen")
@patch("zotero_cli.core.services.attachment_service.os.remove")
@patch("zotero_cli.core.services.attachment_service.os.path.exists")
def test_attach_pdf_from_existing_url(
    mock_exists, mock_remove, mock_fdopen, mock_mkstemp, mock_get,
    service, mock_gateway
):
    mock_exists.return_value = True
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="T", url="http://example.com/paper.pdf")
    mock_gateway.get_item.return_value = item
    mock_gateway.get_item_children.return_value = []
    
    # Download setup
    mock_mkstemp.return_value = (123, "/tmp/temp.pdf")
    mock_fdopen.return_value.__enter__.return_value = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [b"pdf"]
    mock_get.return_value = mock_response
    
    mock_gateway.upload_attachment.return_value = True
    
    success = service.attach_pdf_to_item("K1")
    
    assert success is True
    mock_get.assert_called_with("http://example.com/paper.pdf", stream=True, timeout=30)
    mock_gateway.upload_attachment.assert_called_with("K1", "/tmp/temp.pdf")

@patch("zotero_cli.core.services.attachment_service.requests.get")
@patch("zotero_cli.core.services.attachment_service.tempfile.mkstemp")
@patch("zotero_cli.core.services.attachment_service.os.fdopen")
@patch("zotero_cli.core.services.attachment_service.os.remove")
@patch("zotero_cli.core.services.attachment_service.os.path.exists")
def test_attach_pdf_fallback_to_generic_url(
    mock_exists, mock_remove, mock_fdopen, mock_mkstemp, mock_get,
    service, mock_gateway, mock_aggregator
):
    mock_exists.return_value = True
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="T", doi="10.1/test")
    mock_gateway.get_item.return_value = item
    mock_gateway.get_item_children.return_value = []
    
    # Metadata with NO pdf_url but a PDF-looking url
    metadata = ResearchPaper(title="T", abstract="", url="http://example.com/actual_pdf.pdf", pdf_url=None)
    mock_aggregator.get_enriched_metadata.return_value = metadata
    
    # Download setup
    mock_mkstemp.return_value = (123, "/tmp/temp.pdf")
    mock_fdopen.return_value.__enter__.return_value = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [b"pdf"]
    mock_get.return_value = mock_response
    
    mock_gateway.upload_attachment.return_value = True
    
    success = service.attach_pdf_to_item("K1")
    
    assert success is True
    mock_get.assert_called_with("http://example.com/actual_pdf.pdf", stream=True, timeout=30)
