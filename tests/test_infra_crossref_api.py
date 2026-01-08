import unittest
from unittest.mock import patch, Mock
import requests
from zotero_cli.infra.crossref_api import CrossRefAPIClient

class TestCrossRefAPIClient(unittest.TestCase):
    def setUp(self):
        self.client = CrossRefAPIClient()

    @patch('requests.get')
    def test_get_paper_metadata_success(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "message": {
                "title": ["Test Paper"],
                "abstract": "Test Abstract",
                "author": [{"given": "John", "family": "Doe"}, {"given": "Jane", "family": "Smith"}],
                "published-print": {"date-parts": [[2023]]},
                "DOI": "10.1000/main.paper",
                "URL": "http://dx.doi.org/10.1000/main.paper",
                "is-referenced-by-count": 42,
                "reference": [
                    {"DOI": "10.1000/cited.paper.1"},
                    {"unrelated_field": "some_value"},
                    {"DOI": "10.1000/cited.paper.2"},
                    {"DOI": ""} 
                ]
            }
        }
        mock_get.return_value = mock_response

        doi = "10.1000/main.paper"
        metadata = self.client.get_paper_metadata(doi)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.title, "Test Paper")
        self.assertEqual(metadata.authors, ["John Doe", "Jane Smith"])
        self.assertEqual(metadata.year, "2023")
        self.assertEqual(metadata.doi, "10.1000/main.paper")
        self.assertEqual(metadata.citation_count, 42)
        self.assertEqual(len(metadata.references), 2)
        self.assertIn("10.1000/cited.paper.1", metadata.references)
        self.assertIn("10.1000/cited.paper.2", metadata.references)

    @patch('requests.get')
    def test_get_paper_metadata_api_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        doi = "10.1000/error.paper"
        metadata = self.client.get_paper_metadata(doi)

        self.assertIsNone(metadata)

if __name__ == '__main__':
    unittest.main()


    def test_get_references_by_doi_no_reference_key(self):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"message": {"other_sub_key": "other_value"}} # Missing "reference" key
        
        with patch('requests.get', return_value=mock_response):
            references = self.client.get_references_by_doi("10.123/missing.reference")
            self.assertEqual(references, [])


if __name__ == '__main__':
    unittest.main()
