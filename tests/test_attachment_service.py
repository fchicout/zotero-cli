import unittest
from unittest.mock import Mock, patch, MagicMock
import os
from paper2zotero.core.services.attachment_service import AttachmentService
from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.services.metadata_aggregator import MetadataAggregatorService
from paper2zotero.core.models import ResearchPaper
from paper2zotero.core.zotero_item import ZoteroItem

class TestAttachmentService(unittest.TestCase):
    def setUp(self):
        self.mock_gateway = Mock(spec=ZoteroGateway)
        self.mock_aggregator = Mock(spec=MetadataAggregatorService)
        self.service = AttachmentService(self.mock_gateway, self.mock_aggregator)

    def _create_item(self, key="KEY1", doi="10.1234/test"):
        return ZoteroItem(key=key, version=1, item_type="journalArticle", title="Test Paper", doi=doi)

    def test_collection_not_found(self):
        self.mock_gateway.get_collection_id_by_name.return_value = None
        count = self.service.attach_pdfs_to_collection("NonExistent")
        self.assertEqual(count, 0)
        self.mock_gateway.get_items_in_collection.assert_not_called()

    @patch('paper2zotero.core.services.attachment_service.requests.get')
    @patch('paper2zotero.core.services.attachment_service.os.remove')
    @patch('paper2zotero.core.services.attachment_service.tempfile.mkstemp')
    @patch('paper2zotero.core.services.attachment_service.os.fdopen')
    @patch('paper2zotero.core.services.attachment_service.os.path.exists')
    def test_attach_pdf_success(self, mock_exists, mock_fdopen, mock_mkstemp, mock_remove, mock_get):
        # Setup mocks
        mock_exists.return_value = True
        self.mock_gateway.get_collection_id_by_name.return_value = "COL1"
        item = self._create_item()
        self.mock_gateway.get_items_in_collection.return_value = iter([item])
        
        # 1. No existing PDF
        self.mock_gateway.get_item_children.return_value = []
        
        # 2. Metadata found with PDF URL
        metadata = ResearchPaper(title="Test", abstract="", pdf_url="http://example.com/paper.pdf")
        self.mock_aggregator.get_enriched_metadata.return_value = metadata
        
        # 3. Download setup
        mock_mkstemp.return_value = (123, "/tmp/temp.pdf")
        mock_file = MagicMock()
        mock_fdopen.return_value.__enter__.return_value = mock_file
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"pdf-content"]
        mock_get.return_value = mock_response

        # 4. Upload success
        self.mock_gateway.upload_attachment.return_value = True

        # Run
        count = self.service.attach_pdfs_to_collection("TestCollection")
        
        # Assertions
        self.assertEqual(count, 1)
        self.mock_gateway.get_collection_id_by_name.assert_called_with("TestCollection")
        self.mock_gateway.get_item_children.assert_called_with("KEY1")
        self.mock_aggregator.get_enriched_metadata.assert_called_with("10.1234/test")
        mock_get.assert_called_with("http://example.com/paper.pdf", stream=True, timeout=30)
        self.mock_gateway.upload_attachment.assert_called_with("KEY1", "/tmp/temp.pdf")
        mock_remove.assert_called_with("/tmp/temp.pdf")

    def test_already_has_pdf(self):
        self.mock_gateway.get_collection_id_by_name.return_value = "COL1"
        item = self._create_item()
        self.mock_gateway.get_items_in_collection.return_value = iter([item])
        
        # Simulate existing PDF attachment
        attachment = {
            'data': {
                'itemType': 'attachment',
                'linkMode': 'imported_file',
                'contentType': 'application/pdf'
            }
        }
        self.mock_gateway.get_item_children.return_value = [attachment]
        
        count = self.service.attach_pdfs_to_collection("TestCollection")
        
        self.assertEqual(count, 0)
        self.mock_aggregator.get_enriched_metadata.assert_not_called()

    def test_no_identifier(self):
        self.mock_gateway.get_collection_id_by_name.return_value = "COL1"
        item = ZoteroItem(key="KEY1", version=1, item_type="note") # No DOI/ArXiv
        self.mock_gateway.get_items_in_collection.return_value = iter([item])
        self.mock_gateway.get_item_children.return_value = []

        count = self.service.attach_pdfs_to_collection("TestCollection")
        
        self.assertEqual(count, 0)
        self.mock_aggregator.get_enriched_metadata.assert_not_called()

    @patch('paper2zotero.core.services.attachment_service.requests.get')
    def test_download_failure(self, mock_get):
        self.mock_gateway.get_collection_id_by_name.return_value = "COL1"
        item = self._create_item()
        self.mock_gateway.get_items_in_collection.return_value = iter([item])
        self.mock_gateway.get_item_children.return_value = []
        
        metadata = ResearchPaper(title="Test", abstract="", pdf_url="http://example.com/fail.pdf")
        self.mock_aggregator.get_enriched_metadata.return_value = metadata
        
        # Simulate download error
        mock_get.side_effect = Exception("Download failed")

        count = self.service.attach_pdfs_to_collection("TestCollection")
        
        self.assertEqual(count, 0)
        self.mock_gateway.upload_attachment.assert_not_called()

if __name__ == '__main__':
    unittest.main()
