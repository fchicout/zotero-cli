import unittest
from unittest.mock import patch, Mock
import requests
from zotero_cli.infra.unpaywall_api import UnpaywallAPIClient

class TestUnpaywallAPIClient(unittest.TestCase):
    def setUp(self):
        self.client = UnpaywallAPIClient()

    @patch('requests.get')
    def test_get_paper_metadata_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "doi": "10.1234/test",
            "doi_url": "https://doi.org/10.1234/test",
            "title": "Open Access Paper",
            "year": 2024,
            "publisher": "Open Publisher",
            "z_authors": [{"given": "Open", "family": "Scientist"}],
            "best_oa_location": {
                "url_for_pdf": "https://example.com/paper.pdf"
            }
        }
        mock_get.return_value = mock_response

        metadata = self.client.get_paper_metadata("10.1234/test")
        
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.title, "Open Access Paper")
        self.assertEqual(metadata.doi, "10.1234/test")
        self.assertEqual(metadata.pdf_url, "https://example.com/paper.pdf")
        self.assertEqual(metadata.year, "2024")
        self.assertEqual(metadata.authors, ["Open Scientist"])

    @patch('requests.get')
    def test_get_paper_metadata_no_oa(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "doi": "10.1234/closed",
            "title": "Closed Paper",
            "best_oa_location": None,
            "oa_locations": []
        }
        mock_get.return_value = mock_response

        metadata = self.client.get_paper_metadata("10.1234/closed")
        
        self.assertIsNotNone(metadata)
        self.assertIsNone(metadata.pdf_url)

    def test_get_paper_metadata_invalid_doi(self):
        metadata = self.client.get_paper_metadata("not-a-doi")
        self.assertIsNone(metadata)

if __name__ == '__main__':
    unittest.main()
