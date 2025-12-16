import unittest
from unittest.mock import Mock, patch, mock_open
from paper2zotero.infra.bibtex_lib import BibtexLibGateway
from paper2zotero.core.models import ResearchPaper

class TestBibtexLibGateway(unittest.TestCase):
    @patch('paper2zotero.infra.bibtex_lib.bibtexparser.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_success(self, mock_file, mock_load):
        # Setup mock BibDatabase
        mock_db = Mock()
        mock_db.entries = [
            {
                'title': '{My Paper}',
                'author': 'Doe, John and Smith, Jane',
                'year': '2023',
                'journal': 'Journal of AI',
                'doi': '10.1000/1',
                'abstract': 'Abstract here'
            },
            {
                'title': 'Another Paper',
                'author': 'Single Author',
                'eprint': '2301.00001',
                'archivePrefix': 'arXiv'
            }
        ]
        mock_load.return_value = mock_db

        gateway = BibtexLibGateway()
        papers = list(gateway.parse_file("test.bib"))

        self.assertEqual(len(papers), 2)
        
        self.assertIsInstance(papers[0], ResearchPaper)
        self.assertEqual(papers[0].title, "My Paper")
        self.assertEqual(papers[0].authors, ["Doe, John", "Smith, Jane"])
        self.assertEqual(papers[0].year, "2023")
        self.assertEqual(papers[0].publication, "Journal of AI")
        self.assertEqual(papers[0].doi, "10.1000/1")

        self.assertIsInstance(papers[1], ResearchPaper)
        self.assertEqual(papers[1].authors, ["Single Author"])
        self.assertEqual(papers[1].arxiv_id, "2301.00001")

if __name__ == '__main__':
    unittest.main()
