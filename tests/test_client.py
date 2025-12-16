import unittest
from io import StringIO
from unittest.mock import Mock, patch, MagicMock
from paper2zotero.client import Arxiv2ZoteroClient, CollectionNotFoundError
from paper2zotero.core.interfaces import ZoteroGateway, ArxivGateway
from paper2zotero.core.models import ArxivPaper

class TestArxiv2ZoteroClient(unittest.TestCase):
    def setUp(self):
        self.mock_zotero_gateway = Mock(spec=ZoteroGateway)
        self.mock_arxiv_gateway = Mock(spec=ArxivGateway)
        self.client = Arxiv2ZoteroClient(
            zotero_gateway=self.mock_zotero_gateway, 
            arxiv_gateway=self.mock_arxiv_gateway
        )

    # --- Tests for add_paper ---
    def test_add_paper_success(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_123"
        self.mock_zotero_gateway.create_item.return_value = True

        result = self.client.add_paper("2301.00001", "Test Abstract", "Test Title", "My Folder")

        self.assertTrue(result)
        self.mock_zotero_gateway.get_collection_id_by_name.assert_called_with("My Folder")
        self.mock_zotero_gateway.create_item.assert_called_once()
        
        args, _ = self.mock_zotero_gateway.create_item.call_args
        paper_arg = args[0]
        collection_id_arg = args[1]
        
        self.assertIsInstance(paper_arg, ArxivPaper)
        self.assertEqual(paper_arg.arxiv_id, "2301.00001")
        self.assertEqual(collection_id_arg, "COLL_123")

    def test_add_paper_collection_not_found(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = None

        with self.assertRaises(CollectionNotFoundError):
            self.client.add_paper("2301.00001", "Abs", "Title", "Missing Folder")

        self.mock_zotero_gateway.create_item.assert_not_called()

    def test_add_paper_creation_failure(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_123"
        self.mock_zotero_gateway.create_item.return_value = False

        result = self.client.add_paper("2301.00001", "Abs", "Title", "My Folder")

        self.assertFalse(result)

    # --- Tests for import_from_query ---
    def test_import_from_query_success(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_456"
        self.mock_zotero_gateway.create_item.return_value = True

        mock_arxiv_papers = [
            ArxivPaper(arxiv_id="1", title="Paper 1", abstract="Abs 1"),
            ArxivPaper(arxiv_id="2", title="Paper 2", abstract="Abs 2"),
        ]
        self.mock_arxiv_gateway.search.return_value = iter(mock_arxiv_papers)

        imported_count = self.client.import_from_query("test query", "Bulk Folder", limit=2)

        self.assertEqual(imported_count, 2)
        self.mock_zotero_gateway.get_collection_id_by_name.assert_called_with("Bulk Folder")
        self.mock_arxiv_gateway.search.assert_called_once_with("test query", 2)
        self.assertEqual(self.mock_zotero_gateway.create_item.call_count, 2)
        # Check if create_item was called with correct papers and collection_id
        calls = self.mock_zotero_gateway.create_item.call_args_list
        self.assertEqual(calls[0].args[0], mock_arxiv_papers[0])
        self.assertEqual(calls[0].args[1], "COLL_456")
        self.assertEqual(calls[1].args[0], mock_arxiv_papers[1])
        self.assertEqual(calls[1].args[1], "COLL_456")

    def test_import_from_query_collection_not_found(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = None

        with self.assertRaises(CollectionNotFoundError):
            self.client.import_from_query("test query", "Missing Bulk Folder")
        
        self.mock_arxiv_gateway.search.assert_not_called()
        self.mock_zotero_gateway.create_item.assert_not_called()

    def test_import_from_query_arxiv_gateway_not_provided(self):
        client_no_arxiv = Arxiv2ZoteroClient(zotero_gateway=self.mock_zotero_gateway)
        with self.assertRaises(ValueError):
            client_no_arxiv.import_from_query("test query", "Some Folder")

    def test_import_from_query_partial_success(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_456"
        
        # Simulate one success and one failure
        self.mock_zotero_gateway.create_item.side_effect = [True, False]

        mock_arxiv_papers = [
            ArxivPaper(arxiv_id="1", title="Paper 1", abstract="Abs 1"),
            ArxivPaper(arxiv_id="2", title="Paper 2", abstract="Abs 2"),
        ]
        self.mock_arxiv_gateway.search.return_value = iter(mock_arxiv_papers)

        imported_count = self.client.import_from_query("test query", "Bulk Folder", limit=2)
        self.assertEqual(imported_count, 1)
        self.assertEqual(self.mock_zotero_gateway.create_item.call_count, 2)
        
    def test_import_from_query_verbose_output(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_456"
        self.mock_zotero_gateway.create_item.return_value = True

        mock_arxiv_papers = [
            ArxivPaper(arxiv_id="1", title="Paper 1", abstract="Abs 1"),
        ]
        self.mock_arxiv_gateway.search.return_value = iter(mock_arxiv_papers)

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            self.client.import_from_query("test query", "Bulk Folder", limit=1, verbose=True)
            output = mock_stdout.getvalue()
            self.assertIn("Searching arXiv for: 'test query'", output)
            self.assertIn("Adding: Paper 1...", output)

if __name__ == '__main__':
    unittest.main()