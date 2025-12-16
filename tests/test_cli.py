import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys
from arxiv2zotero.cli.main import main
from arxiv2zotero.client import CollectionNotFoundError

class TestCLI(unittest.TestCase):
    
    @patch('arxiv2zotero.cli.main.Arxiv2ZoteroClient')
    @patch('arxiv2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_success(self, mock_stdout, MockZoteroAPI, MockArxivClient):
        # Setup mocks
        mock_client_instance = MockArxivClient.return_value
        mock_client_instance.add_paper.return_value = True

        # Simulate command line arguments
        test_args = ['program', '--arxiv-id', '123', '--title', 'T', '--abstract', 'A', '--folder', 'F']
        with patch.object(sys, 'argv', test_args):
            main()

        # Assertions
        mock_client_instance.add_paper.assert_called_once_with('123', 'A', 'T', 'F')
        self.assertIn("Successfully added", mock_stdout.getvalue())

    @patch('arxiv2zotero.cli.main.Arxiv2ZoteroClient')
    @patch('arxiv2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_collection_not_found(self, mock_stdout, MockZoteroAPI, MockArxivClient):
        # Setup mocks
        mock_client_instance = MockArxivClient.return_value
        mock_client_instance.add_paper.side_effect = CollectionNotFoundError("Not found")

        # Simulate command line arguments
        test_args = ['program', '--arxiv-id', '123', '--title', 'T', '--abstract', 'A', '--folder', 'F']
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

        self.assertIn("Error: Not found", mock_stdout.getvalue())

    @patch.dict('os.environ', {}, clear=True)
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_missing_env_vars(self, mock_stdout):
        test_args = ['program', '--arxiv-id', '123', '--title', 'T', '--abstract', 'A', '--folder', 'F']
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)
        
        self.assertIn("Error: ZOTERO_API_KEY environment variable not set", mock_stdout.getvalue())

if __name__ == '__main__':
    unittest.main()
