import unittest
import requests
from unittest.mock import Mock, patch
from paper2zotero.infra.zotero_api import ZoteroAPIClient
from paper2zotero.core.models import ArxivPaper

class TestZoteroAPIClient(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_api_key"
        self.group_id = "1234567"
        self.client = ZoteroAPIClient(self.api_key, self.group_id)

    @patch('requests.get')
    def test_get_collection_id_by_name_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"key": "COLL_1", "data": {"name": "Wrong Folder"}},
            {"key": "COLL_2", "data": {"name": "Target Folder"}},
            {"key": "COLL_3", "data": {"name": "Another Folder"}},
        ]
        mock_get.return_value = mock_response

        collection_id = self.client.get_collection_id_by_name("Target Folder")
        self.assertEqual(collection_id, "COLL_2")
        mock_get.assert_called_once_with(
            f"{self.client.BASE_URL}/groups/{self.group_id}/collections",
            headers=self.client.headers,
            params={'limit': 100}
        )

    @patch('requests.get')
    def test_get_collection_id_by_name_not_found(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"key": "COLL_1", "data": {"name": "Wrong Folder"}},
        ]
        mock_get.return_value = mock_response

        collection_id = self.client.get_collection_id_by_name("NonExistent Folder")
        self.assertIsNone(collection_id)

    @patch('requests.get')
    def test_get_collection_id_by_name_api_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("API Error")

        collection_id = self.client.get_collection_id_by_name("Target Folder")
        self.assertIsNone(collection_id)

    @patch('requests.post')
    def test_create_item_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        paper = ArxivPaper(arxiv_id="2301.00001", title="Test Title", abstract="Test Abstract")
        collection_id = "COLL_123"
        result = self.client.create_item(paper, collection_id)

        self.assertTrue(result)
        expected_payload = [{
            "itemType": "journalArticle",
            "title": paper.title,
            "abstractNote": paper.abstract,
            "url": f"https://arxiv.org/abs/{paper.arxiv_id}",
            "libraryCatalog": "arXiv",
            "accessDate": "",
            "collections": [collection_id]
        }]
        mock_post.assert_called_once_with(
            f"{self.client.BASE_URL}/groups/{self.group_id}/items",
            headers=self.client.headers,
            json=expected_payload
        )

    @patch('requests.post')
    def test_create_item_api_error(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.RequestException("Bad Request")
        mock_post.return_value = mock_response

        paper = ArxivPaper(arxiv_id="2301.00001", title="Test Title", abstract="Test Abstract")
        collection_id = "COLL_123"
        result = self.client.create_item(paper, collection_id)

        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
