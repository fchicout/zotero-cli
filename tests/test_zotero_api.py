import unittest
from unittest.mock import Mock, patch
from paper2zotero.infra.zotero_api import ZoteroAPIClient
from paper2zotero.core.models import ResearchPaper
import requests

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

    @patch('requests.post')
    def test_create_collection_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'successful': {'0': {'key': 'NEW_COLL_KEY'}}}
        mock_post.return_value = mock_response

        collection_id = self.client.create_collection("New Folder")
        self.assertEqual(collection_id, "NEW_COLL_KEY")
        
        expected_payload = [{"name": "New Folder"}]
        mock_post.assert_called_once_with(
            f"{self.client.BASE_URL}/groups/{self.group_id}/collections",
            headers=self.client.headers,
            json=expected_payload
        )

    @patch('requests.post')
    def test_create_item_full_metadata(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        paper = ResearchPaper(
            title="Test Title", 
            abstract="Test Abstract", 
            authors=["John Doe", "Jane Smith"],
            doi="10.1000/1",
            publication="Journal of Testing",
            year="2023",
            url="http://example.com"
        )
        collection_id = "COLL_123"
        result = self.client.create_item(paper, collection_id)

        self.assertTrue(result)
        expected_payload = [{
            "itemType": "journalArticle",
            "title": "Test Title",
            "abstractNote": "Test Abstract",
            "creators": [
                {"creatorType": "author", "firstName": "John", "lastName": "Doe"},
                {"creatorType": "author", "firstName": "Jane", "lastName": "Smith"}
            ],
            "collections": ["COLL_123"],
            "url": "http://example.com",
            "DOI": "10.1000/1",
            "publicationTitle": "Journal of Testing",
            "date": "2023"
        }]
        mock_post.assert_called_once_with(
            f"{self.client.BASE_URL}/groups/{self.group_id}/items",
            headers=self.client.headers,
            json=expected_payload
        )

if __name__ == '__main__':
    unittest.main()
