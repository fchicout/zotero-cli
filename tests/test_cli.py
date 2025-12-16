import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO
import sys
from paper2zotero.cli.main import main
from paper2zotero.client import CollectionNotFoundError

class TestCLI(unittest.TestCase):
    
    @patch('paper2zotero.cli.main.PaperImporterClient')
    @patch('paper2zotero.cli.main.ArxivLibGateway')
    @patch('paper2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    @patch('sys.stdout', new_callable=StringIO)
    def test_add_command_success(self, mock_stdout, MockZoteroAPI, MockArxivLibGateway, MockPaperClient):
        # Setup mocks
        mock_client_instance = MockPaperClient.return_value
        mock_client_instance.add_paper.return_value = True

        # Simulate 'add' subcommand
        test_args = ['program', 'add', '--arxiv-id', '123', '--title', 'T', '--abstract', 'A', '--folder', 'F']
        with patch.object(sys, 'argv', test_args):
            main()

        # Assertions
        mock_client_instance.add_paper.assert_called_once_with('123', 'A', 'T', 'F')
        self.assertIn("Successfully added", mock_stdout.getvalue())

    @patch('paper2zotero.cli.main.PaperImporterClient')
    @patch('paper2zotero.cli.main.ArxivLibGateway')
    @patch('paper2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    @patch('sys.stdout', new_callable=StringIO)
    def test_import_command_success(self, mock_stdout, MockZoteroAPI, MockArxivLibGateway, MockPaperClient):
        # Setup mocks
        mock_client_instance = MockPaperClient.return_value
        mock_client_instance.import_from_query.return_value = 5

        # Simulate 'import' subcommand
        test_args = ['program', 'import', '--query', 'test query', '--folder', 'F', '--limit', '10']
        with patch.object(sys, 'argv', test_args):
            main()

        # Assertions
        mock_client_instance.import_from_query.assert_called_once_with('test query', 'F', 10, False)
        self.assertIn("Successfully imported 5 papers", mock_stdout.getvalue())

    @patch('paper2zotero.cli.main.PaperImporterClient')
    @patch('paper2zotero.cli.main.ArxivLibGateway')
    @patch('paper2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    @patch('sys.stdout', new_callable=StringIO)
    def test_import_command_verbose(self, mock_stdout, MockZoteroAPI, MockArxivLibGateway, MockPaperClient):
        # Setup mocks
        mock_client_instance = MockPaperClient.return_value
        mock_client_instance.import_from_query.return_value = 5

        # Simulate 'import' subcommand with verbose
        test_args = ['program', 'import', '--query', 'test query', '--folder', 'F', '--verbose']
        with patch.object(sys, 'argv', test_args):
            main()

        # Assertions
        mock_client_instance.import_from_query.assert_called_once_with('test query', 'F', 100, True)

    @patch('paper2zotero.cli.main.PaperImporterClient')
    @patch('paper2zotero.cli.main.ArxivLibGateway')
    @patch('paper2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    @patch('sys.stderr', new_callable=StringIO)
    @patch('sys.stdout', new_callable=StringIO)
    def test_add_command_collection_not_found(self, mock_stdout, mock_stderr, MockZoteroAPI, MockArxivLibGateway, MockPaperClient):
        # Setup mocks
        mock_client_instance = MockPaperClient.return_value
        mock_client_instance.add_paper.side_effect = CollectionNotFoundError("Not found")

        # Simulate 'add' subcommand
        test_args = ['program', 'add', '--arxiv-id', '123', '--title', 'T', '--abstract', 'A', '--folder', 'F']
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

        self.assertIn("Error: Not found", mock_stderr.getvalue())

    @patch('paper2zotero.cli.main.PaperImporterClient')
    @patch('paper2zotero.cli.main.ArxivLibGateway')
    @patch('paper2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    def test_import_command_file_input(self, MockZoteroAPI, MockArxivLibGateway, MockPaperClient):
        # Setup mocks
        mock_client_instance = MockPaperClient.return_value
        mock_client_instance.import_from_query.return_value = 1

        # Simulate file input
        file_content = "query from file"
        with patch('builtins.open', mock_open(read_data=file_content)):
            test_args = ['program', 'import', '--file', 'query.txt', '--folder', 'F']
            with patch.object(sys, 'argv', test_args):
                main()
        
        mock_client_instance.import_from_query.assert_called_once_with('query from file', 'F', 100, False)

    @patch('paper2zotero.cli.main.PaperImporterClient')
    @patch('paper2zotero.cli.main.ArxivLibGateway')
    @patch('paper2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    def test_import_command_pipe_input(self, MockZoteroAPI, MockArxivLibGateway, MockPaperClient):
        # Setup mocks
        mock_client_instance = MockPaperClient.return_value
        mock_client_instance.import_from_query.return_value = 1

        # Simulate pipe input
        test_args = ['program', 'import', '--folder', 'F']
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdin', StringIO('query from pipe')):
                with patch('sys.stdin.isatty', return_value=False):
                    main()
        
        mock_client_instance.import_from_query.assert_called_once_with('query from pipe', 'F', 100, False)

    @patch('paper2zotero.cli.main.PaperImporterClient')
    @patch('paper2zotero.cli.main.ArxivLibGateway')
    @patch('paper2zotero.cli.main.ZoteroAPIClient')
    @patch.dict('os.environ', {'ZOTERO_API_KEY': 'key', 'ZOTERO_TARGET_GROUP': 'https://zotero/groups/123/name'})
    @patch('sys.stderr', new_callable=StringIO)
    def test_import_command_no_query(self, mock_stderr, MockZoteroAPI, MockArxivLibGateway, MockPaperClient):
        # Simulate missing query
        test_args = ['program', 'import', '--folder', 'F']
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdin.isatty', return_value=True): # No pipe
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 1)
        
        self.assertIn("Error: No query provided", mock_stderr.getvalue())

if __name__ == '__main__':
    unittest.main()