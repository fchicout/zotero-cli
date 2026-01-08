import unittest
from unittest.mock import patch, Mock
import requests
from zotero_cli.infra.zotero_api import ZoteroAPIClient

class TestZoteroAPIClientMove(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_key"
        self.group_id = "12345"
        self.client = ZoteroAPIClient(self.api_key, self.group_id)
        # Mock the session object directly
        self.client.session = Mock(spec=requests.Session)
        self.client.session.headers = {} # Mock headers dict

    def test_update_item_collections_success(self):
        # Setup mock response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None  # No exception
        mock_response.headers = {'Last-Modified-Version': '43'} # Added valid version
        self.client.session.patch.return_value = mock_response

        # Inputs
        item_key = "ABC12345"
        version = 42
        self.client.last_library_version = version # Set internal state
        new_collections = ["COL1", "COL2"]

        # Action
        result = self.client.update_item_collections(item_key, version, new_collections)

        # Assertion
        self.assertTrue(result)
        
        expected_url = f"https://api.zotero.org/groups/{self.group_id}/items/{item_key}"
        # Since session handles headers, we check if headers were passed to patch, 
        # but logic only adds If-Match to the call, other headers are on session.
        # Let's verify If-Match is passed.
        
        call_args = self.client.session.patch.call_args
        self.assertEqual(call_args[0][0], expected_url)
        self.assertEqual(call_args[1]['json'], {'collections': new_collections})
        self.assertEqual(call_args[1]['headers']['If-Unmodified-Since-Version'], str(version))

    def test_update_item_collections_failure(self):
        # Setup mock exception
        self.client.session.patch.side_effect = requests.exceptions.RequestException("API Error")

        # Action
        result = self.client.update_item_collections("ABC", 1, [])

        # Assertion
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
