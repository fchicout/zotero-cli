import unittest
from unittest.mock import Mock, ANY, patch
from io import StringIO
from paper2zotero.client import PaperImporterClient, CollectionNotFoundError
from paper2zotero.core.interfaces import ZoteroGateway, ArxivGateway
from paper2zotero.core.models import ResearchPaper

class TestPaperImporterClient(unittest.TestCase):
    def setUp(self):
        self.mock_zotero_gateway = Mock(spec=ZoteroGateway)
        self.mock_arxiv_gateway = Mock(spec=ArxivGateway)
        self.client = PaperImporterClient(
            zotero_gateway=self.mock_zotero_gateway, 
            arxiv_gateway=self.mock_arxiv_gateway
        )

    def test_add_paper_success(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_123"
        self.mock_zotero_gateway.create_item.return_value = True

        result = self.client.add_paper("2301.00001", "Test Abstract", "Test Title", "My Folder")

        self.assertTrue(result)
        self.mock_zotero_gateway.get_collection_id_by_name.assert_called_with("My Folder")
        self.mock_zotero_gateway.create_item.assert_called_once()

    def test_add_paper_create_collection(self):
        # Setup: Collection not found, so create it
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = None
        self.mock_zotero_gateway.create_collection.return_value = "NEW_COLL_KEY"
        self.mock_zotero_gateway.create_item.return_value = True

        result = self.client.add_paper("2301.00001", "Abs", "Title", "New Folder")

        self.assertTrue(result)
        self.mock_zotero_gateway.get_collection_id_by_name.assert_called_with("New Folder")
        self.mock_zotero_gateway.create_collection.assert_called_with("New Folder")
        self.mock_zotero_gateway.create_item.assert_called_once()
        # Verify creating item in new collection
        args, _ = self.mock_zotero_gateway.create_item.call_args
        self.assertEqual(args[1], "NEW_COLL_KEY")

    def test_add_paper_collection_creation_fails(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = None
        self.mock_zotero_gateway.create_collection.return_value = None

        with self.assertRaises(CollectionNotFoundError):
            self.client.add_paper("2301.00001", "Abs", "Title", "Fail Folder")

    def test_import_from_query_success(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_456"
        self.mock_zotero_gateway.create_item.return_value = True
        
        mock_papers = [ResearchPaper(title="P1", abstract="A1"), ResearchPaper(title="P2", abstract="A2")]
        self.mock_arxiv_gateway.search.return_value = iter(mock_papers)

        count = self.client.import_from_query("q", "F", 2)
        self.assertEqual(count, 2)

if __name__ == '__main__':
    unittest.main()