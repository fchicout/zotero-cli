import unittest
from unittest.mock import Mock, patch
from zotero_cli.infra.zotero_api import ZoteroAPIClient
from zotero_cli.core.models import ResearchPaper
import requests

class TestZoteroAPIClient(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_api_key"
        self.group_id = "1234567"
        self.client = ZoteroAPIClient(self.api_key, self.group_id)
        # Mock the session object directly
        self.client.session = Mock(spec=requests.Session)
        self.client.session.headers = {} # Mock headers dict

    def test_get_collection_id_by_name_success(self):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"key": "COLL_1", "data": {"name": "Wrong Folder"}},
            {"key": "COLL_2", "data": {"name": "Target Folder"}},
            {"key": "COLL_3", "data": {"name": "Another Folder"}},
        ]
        # Fix: ensure headers.get returns None by default or a specific value
        mock_response.headers = {} 
        self.client.session.get.return_value = mock_response

        collection_id = self.client.get_collection_id_by_name("Target Folder")
        self.assertEqual(collection_id, "COLL_2")

    def test_create_collection_success(self):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'successful': {'0': {'key': 'NEW_COLL_KEY'}}}
        mock_response.headers = {} # Fix
        self.client.session.post.return_value = mock_response

        collection_id = self.client.create_collection("New Folder")
        self.assertEqual(collection_id, "NEW_COLL_KEY")
        
        expected_payload = [{"name": "New Folder"}]
        self.client.session.post.assert_called_once_with(
            f"{self.client.BASE_URL}/groups/{self.group_id}/collections",
            json=expected_payload
        )

    def test_create_item_full_metadata(self):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {} # Fix
        self.client.session.post.return_value = mock_response

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
        self.client.session.post.assert_called_once_with(
            f"{self.client.BASE_URL}/groups/{self.group_id}/items",
            json=expected_payload
        )

    def test_delete_item_success(self):
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.headers = {'Last-Modified-Version': '11'} # Provide a version
        self.client.session.delete.return_value = mock_response
        
        # Set initial library version
        self.client.last_library_version = 10

        success = self.client.delete_item("ITEM_KEY", 10)
        
        self.assertTrue(success)
        self.client.session.delete.assert_called_once()
        args, kwargs = self.client.session.delete.call_args
        self.assertEqual(args[0], f"{self.client.BASE_URL}/groups/{self.group_id}/items/ITEM_KEY")
        self.assertEqual(kwargs['headers']['If-Unmodified-Since-Version'], '10')

    def test_delete_item_version_conflict_retry(self):
        # First call returns 412, second returns 204
        mock_response_412 = Mock()
        mock_response_412.status_code = 412
        mock_response_412.headers = {'Last-Modified-Version': '11'}
        
        mock_response_204 = Mock()
        mock_response_204.status_code = 204
        mock_response_204.headers = {'Last-Modified-Version': '12'}
        
        self.client.session.delete.side_effect = [mock_response_412, mock_response_204]
        self.client.last_library_version = 10

        success = self.client.delete_item("ITEM_KEY", 10)
        
        self.assertTrue(success)
        self.assertEqual(self.client.session.delete.call_count, 2)
        self.assertEqual(self.client.last_library_version, 12)

if __name__ == '__main__':
    unittest.main()
