import unittest
from unittest.mock import patch, Mock
from paper2zotero.infra.semantic_scholar_api import SemanticScholarAPIClient

class TestSemanticScholarAPIClient(unittest.TestCase):
    def setUp(self):
        self.client = SemanticScholarAPIClient()

    @patch('requests.get')
    def test_get_paper_metadata_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "S2 Title",
            "abstract": "S2 Abstract",
            "year": 2023,
            "venue": "NeurIPS",
            "authors": [{"name": "Author A"}, {"name": "Author B"}],
            "externalIds": {"DOI": "10.1234/s2", "ArXiv": "2301.00001"},
            "references": [
                {"externalIds": {"DOI": "10.5678/ref1"}},
                {"externalIds": {}} # Ref without DOI
            ]
        }
        mock_get.return_value = mock_response

        metadata = self.client.get_paper_metadata("10.1234/s2")
        
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.title, "S2 Title")
        self.assertEqual(metadata.abstract, "S2 Abstract")
        self.assertEqual(metadata.year, "2023")
        self.assertEqual(metadata.doi, "10.1234/s2")
        self.assertEqual(metadata.arxiv_id, "2301.00001")
        self.assertEqual(metadata.authors, ["Author A", "Author B"])
        self.assertEqual(metadata.references, ["10.5678/ref1"])

    @patch('requests.get')
    def test_get_paper_metadata_not_found(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        metadata = self.client.get_paper_metadata("10.0000/missing")
        self.assertIsNone(metadata)

if __name__ == '__main__':
    unittest.main()
