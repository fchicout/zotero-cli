import unittest
from unittest.mock import Mock, patch
from zotero_cli.infra.zotero_api import ZoteroAPIClient
import requests

class TestZoteroAPIClientMetadata(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_key"
        self.group_id = "12345"
        self.client = ZoteroAPIClient(self.api_key, self.group_id)
        self.client.session = Mock(spec=requests.Session)
        self.client.session.headers = {}

    def test_update_item_metadata_success(self):
        mock_response = Mock()
        mock_response.status_code = 204 # No Content
        mock_response.headers = {'Last-Modified-Version': '11'}
        self.client.session.patch.return_value = mock_response

        item_key = "ITEM123"
        version = 10
        self.client.last_library_version = version # Set internal state
        metadata = {"abstractNote": "New abstract"}

        result = self.client.update_item_metadata(item_key, version, metadata)
        
        self.assertTrue(result)
        
        expected_url = f"https://api.zotero.org/groups/{self.group_id}/items/{item_key}"
        call_args = self.client.session.patch.call_args
        self.assertEqual(call_args[0][0], expected_url)
        self.assertEqual(call_args[1]['json'], metadata)
        self.assertEqual(call_args[1]['headers']['If-Unmodified-Since-Version'], str(version))

    def test_update_item_metadata_failure(self):
        self.client.session.patch.side_effect = requests.exceptions.RequestException("API Error")
        
        result = self.client.update_item_metadata("ITEM123", 1, {})
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
