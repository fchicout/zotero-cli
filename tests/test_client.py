import unittest
from unittest.mock import Mock, ANY
from arxiv2zotero.client import Arxiv2ZoteroClient, CollectionNotFoundError
from arxiv2zotero.core.interfaces import ZoteroGateway
from arxiv2zotero.core.models import ArxivPaper

class TestArxiv2ZoteroClient(unittest.TestCase):
    def setUp(self):
        # Create a mock implementation of the gateway
        self.mock_gateway = Mock(spec=ZoteroGateway)
        self.client = Arxiv2ZoteroClient(self.mock_gateway)

    def test_add_paper_success(self):
        # Setup
        self.mock_gateway.get_collection_id_by_name.return_value = "COLL_123"
        self.mock_gateway.create_item.return_value = True

        # Action
        result = self.client.add_paper("2301.00001", "Test Abstract", "Test Title", "My Folder")

        # Assertion
        self.assertTrue(result)
        self.mock_gateway.get_collection_id_by_name.assert_called_with("My Folder")
        self.mock_gateway.create_item.assert_called_once()
        
        # Verify arguments passed to create_item
        args, _ = self.mock_gateway.create_item.call_args
        paper_arg = args[0]
        collection_id_arg = args[1]
        
        self.assertIsInstance(paper_arg, ArxivPaper)
        self.assertEqual(paper_arg.arxiv_id, "2301.00001")
        self.assertEqual(collection_id_arg, "COLL_123")

    def test_add_paper_collection_not_found(self):
        # Setup
        self.mock_gateway.get_collection_id_by_name.return_value = None

        # Action & Assertion
        with self.assertRaises(CollectionNotFoundError):
            self.client.add_paper("2301.00001", "Abs", "Title", "Missing Folder")

        self.mock_gateway.create_item.assert_not_called()

    def test_add_paper_creation_failure(self):
        # Setup
        self.mock_gateway.get_collection_id_by_name.return_value = "COLL_123"
        self.mock_gateway.create_item.return_value = False

        # Action
        result = self.client.add_paper("2301.00001", "Abs", "Title", "My Folder")

        # Assertion
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
