import unittest
from unittest.mock import Mock, patch, mock_open
from zotero_cli.infra.ris_lib import RisLibGateway
from zotero_cli.core.models import ResearchPaper

class TestRisLibGateway(unittest.TestCase):
    @patch('zotero_cli.infra.ris_lib.rispy.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_success(self, mock_file, mock_load):
        # Setup mock rispy entries
        mock_entries = [
            {
                'type_of_reference': 'JOUR', 
                'authors': ['Doe, John', 'Smith, Jane'], 
                'year': '2023', 
                'primary_title': 'A Sample RIS Paper',
                'journal_name': 'Journal of RIS', 
                'abstract': 'This is an abstract.', 
                'doi': '10.1234/ris1', 
                'urls': ['http://ris.example.com']
            },
            {
                'type_of_reference': 'BOOK', 
                'authors': ['Author, A'], 
                'year': '2022', 
                'primary_title': 'Another RIS Entry',
                'secondary_title': 'Book Series', 
                'abstract': 'Book abstract.'
            }
        ]
        mock_load.return_value = mock_entries

        gateway = RisLibGateway()
        papers = list(gateway.parse_file("test.ris"))

        self.assertEqual(len(papers), 2)
        
        self.assertIsInstance(papers[0], ResearchPaper)
        self.assertEqual(papers[0].title, "A Sample RIS Paper")
        self.assertEqual(papers[0].authors, ["Doe, John", "Smith, Jane"])
        self.assertEqual(papers[0].year, "2023")
        self.assertEqual(papers[0].publication, "Journal of RIS")
        self.assertEqual(papers[0].doi, "10.1234/ris1")
        self.assertEqual(papers[0].url, "http://ris.example.com")

        self.assertIsInstance(papers[1], ResearchPaper)
        self.assertEqual(papers[1].title, "Another RIS Entry")
        self.assertEqual(papers[1].authors, ["Author, A"])
        self.assertEqual(papers[1].year, "2022")
        self.assertEqual(papers[1].publication, "Book Series")
        self.assertIsNone(papers[1].doi)
        self.assertIsNone(papers[1].url)

    @patch('zotero_cli.infra.ris_lib.rispy.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_error_handling(self, mock_file, mock_load):
        mock_load.side_effect = Exception("RIS parse error")

        gateway = RisLibGateway()
        papers = list(gateway.parse_file("bad.ris"))
        self.assertEqual(len(papers), 0)


if __name__ == '__main__':
    unittest.main()
