import unittest
from unittest.mock import Mock, patch, mock_open
from paper2zotero.infra.ris_lib import RisLibGateway
from paper2zotero.core.models import ResearchPaper

class TestRisLibGateway(unittest.TestCase):
    @patch('paper2zotero.infra.ris_lib.rispy.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_success(self, mock_file, mock_load):
        # Setup mock rispy entries
        mock_entries = [
            {
                'TY': 'JOUR', 'AU': ['Doe, John', 'Smith, Jane'], 'PY': '2023', 'TI': 'A Sample RIS Paper',
                'JF': 'Journal of RIS', 'AB': 'This is an abstract.', 'DO': '10.1234/ris1', 'UR': 'http://ris.example.com'
            },
            {
                'TY': 'BOOK', 'AU': ['Author, A'], 'YR': '2022', 'T1': 'Another RIS Entry',
                'T2': 'Book Series', 'AB': 'Book abstract.'
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

    @patch('paper2zotero.infra.ris_lib.rispy.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_error_handling(self, mock_file, mock_load):
        mock_load.side_effect = Exception("RIS parse error")

        gateway = RisLibGateway()
        papers = list(gateway.parse_file("bad.ris"))
        self.assertEqual(len(papers), 0)


if __name__ == '__main__':
    unittest.main()
