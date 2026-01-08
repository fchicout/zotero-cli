import unittest
from unittest.mock import Mock, ANY, patch
from io import StringIO
from zotero_cli.client import PaperImporterClient, CollectionNotFoundError
from zotero_cli.core.interfaces import ZoteroGateway, ArxivGateway, BibtexGateway, RisGateway, SpringerCsvGateway, IeeeCsvGateway
from zotero_cli.core.models import ResearchPaper

class TestPaperImporterClient(unittest.TestCase):
    def setUp(self):
        self.mock_zotero_gateway = Mock(spec=ZoteroGateway)
        self.mock_arxiv_gateway = Mock(spec=ArxivGateway)
        self.mock_bibtex_gateway = Mock(spec=BibtexGateway)
        self.mock_ris_gateway = Mock(spec=RisGateway)
        self.mock_springer_csv_gateway = Mock(spec=SpringerCsvGateway) # Add Springer CSV Gateway mock
        self.mock_ieee_csv_gateway = Mock(spec=IeeeCsvGateway) # Add IEEE CSV Gateway mock
        
        self.client = PaperImporterClient(
            zotero_gateway=self.mock_zotero_gateway, 
            arxiv_gateway=self.mock_arxiv_gateway,
            bibtex_gateway=self.mock_bibtex_gateway,
            ris_gateway=self.mock_ris_gateway,
            springer_csv_gateway=self.mock_springer_csv_gateway, # Pass Springer CSV Gateway mock
            ieee_csv_gateway=self.mock_ieee_csv_gateway # Pass IEEE CSV Gateway mock
        )

    def test_add_paper_success(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_123"
        self.mock_zotero_gateway.create_item.return_value = True

        result = self.client.add_paper("2301.00001", "Test Abstract", "Test Title", "My Folder")

        self.assertTrue(result)
        self.mock_zotero_gateway.get_collection_id_by_name.assert_called_with("My Folder")
        self.mock_zotero_gateway.create_item.assert_called_once()

    def test_add_paper_create_collection(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = None
        self.mock_zotero_gateway.create_collection.return_value = "NEW_COLL_KEY"
        self.mock_zotero_gateway.create_item.return_value = True

        result = self.client.add_paper("2301.00001", "Abs", "Title", "New Folder")

        self.assertTrue(result)
        self.mock_zotero_gateway.get_collection_id_by_name.assert_called_with("New Folder")
        self.mock_zotero_gateway.create_collection.assert_called_with("New Folder")
        self.mock_zotero_gateway.create_item.assert_called_once()
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

    def test_import_from_ris_success(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_RIS"
        self.mock_zotero_gateway.create_item.return_value = True

        mock_ris_papers = [
            ResearchPaper(title="RIS Paper 1", abstract="RIS Abs 1"),
            ResearchPaper(title="RIS Paper 2", abstract="RIS Abs 2"),
        ]
        self.mock_ris_gateway.parse_file.return_value = iter(mock_ris_papers)

        imported_count = self.client.import_from_ris("test.ris", "RIS Folder", verbose=False)

        self.assertEqual(imported_count, 2)
        self.mock_zotero_gateway.get_collection_id_by_name.assert_called_with("RIS Folder")
        self.mock_ris_gateway.parse_file.assert_called_once_with("test.ris")
        self.assertEqual(self.mock_zotero_gateway.create_item.call_count, 2)
        calls = self.mock_zotero_gateway.create_item.call_args_list
        self.assertEqual(calls[0].args[0], mock_ris_papers[0])
        self.assertEqual(calls[0].args[1], "COLL_RIS")
        self.assertEqual(calls[1].args[0], mock_ris_papers[1])
        self.assertEqual(calls[1].args[1], "COLL_RIS")

    def test_import_from_ris_ris_gateway_not_provided(self):
        client_no_ris = PaperImporterClient(zotero_gateway=self.mock_zotero_gateway)
        with self.assertRaises(ValueError):
            client_no_ris.import_from_ris("test.ris", "Some Folder")

    def test_import_from_ieee_csv_success(self):
        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_IEEE"
        self.mock_zotero_gateway.create_item.return_value = True

        mock_ieee_papers = [
            ResearchPaper(title="IEEE Paper 1", abstract="IEEE Abs 1", authors=["Author A"]),
            ResearchPaper(title="IEEE Paper 2", abstract="IEEE Abs 2", authors=["Author B"]),
        ]
        self.mock_ieee_csv_gateway.parse_file.return_value = iter(mock_ieee_papers)

        imported_count = self.client.import_from_ieee_csv("test.csv", "IEEE Folder", verbose=False)

        self.assertEqual(imported_count, 2)
        self.mock_zotero_gateway.get_collection_id_by_name.assert_called_with("IEEE Folder")
        self.mock_ieee_csv_gateway.parse_file.assert_called_once_with("test.csv")
        self.assertEqual(self.mock_zotero_gateway.create_item.call_count, 2)
        calls = self.mock_zotero_gateway.create_item.call_args_list
        self.assertEqual(calls[0].args[0], mock_ieee_papers[0])
        self.assertEqual(calls[0].args[1], "COLL_IEEE")
        self.assertEqual(calls[1].args[0], mock_ieee_papers[1])
        self.assertEqual(calls[1].args[1], "COLL_IEEE")

    def test_import_from_ieee_csv_ieee_csv_gateway_not_provided(self):
        client_no_ieee_csv = PaperImporterClient(zotero_gateway=self.mock_zotero_gateway)
        with self.assertRaises(ValueError):
            client_no_ieee_csv.import_from_ieee_csv("test.csv", "Some Folder")

if __name__ == '__main__':
    unittest.main()