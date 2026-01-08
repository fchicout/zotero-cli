import unittest
from unittest.mock import Mock, patch, mock_open
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway
from zotero_cli.core.models import ResearchPaper
import csv

class TestSpringerCsvLibGateway(unittest.TestCase):
    @patch('zotero_cli.infra.springer_csv_lib.csv.DictReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_success(self, mock_file, MockDictReader):
        # Setup mock CSV rows
        mock_csv_rows = [
            {
                'Item Title': 'CyberNER-LLM',
                'Publication Title': 'Information and Communications Security',
                'Book Series Title': '',
                'Journal Volume': '',
                'Journal Issue': '',
                'Item DOI': '10.1007/978-981-95-3543-9_28',
                'Authors': 'Xinzheng LiuWangqun LinZhaoyun Ding', # Will be ignored
                'Publication Year': '2026',
                'URL': 'https://link.springer.com/chapter/10.1007/978-981-95-3543-9_28',
                'Content Type': 'Conference paper'
            },
            {
                'Item Title': 'Generative AI revolution',
                'Publication Title': '',
                'Book Series Title': 'Artificial Intelligence Review',
                'Journal Volume': '',
                'Journal Issue': '',
                'Item DOI': '10.1007/s10462-025-11219-5',
                'Authors': 'Mueen UddinMuhammad Saad Irshad', # Will be ignored
                'Publication Year': '2025',
                'URL': 'https://link.springer.com/article/10.1007/s10462-025-11219-5',
                'Content Type': 'Article'
            }
        ]
        MockDictReader.return_value = mock_csv_rows

        gateway = SpringerCsvLibGateway()
        papers = list(gateway.parse_file("test.csv"))

        self.assertEqual(len(papers), 2)
        
        self.assertIsInstance(papers[0], ResearchPaper)
        self.assertEqual(papers[0].title, "CyberNER-LLM")
        self.assertEqual(papers[0].abstract, "")
        self.assertEqual(papers[0].authors, [])
        self.assertEqual(papers[0].publication, "Information and Communications Security")
        self.assertEqual(papers[0].year, "2026")
        self.assertEqual(papers[0].doi, "10.1007/978-981-95-3543-9_28")
        self.assertEqual(papers[0].url, "https://link.springer.com/chapter/10.1007/978-981-95-3543-9_28")

        self.assertIsInstance(papers[1], ResearchPaper)
        self.assertEqual(papers[1].title, "Generative AI revolution")
        self.assertEqual(papers[1].publication, "Artificial Intelligence Review")
        self.assertEqual(papers[1].year, "2025")
        self.assertEqual(papers[1].doi, "10.1007/s10462-025-11219-5")
        self.assertEqual(papers[1].authors, []) # Still empty

    @patch('zotero_cli.infra.springer_csv_lib.csv.DictReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_empty(self, mock_file, MockDictReader):
        MockDictReader.return_value = []
        gateway = SpringerCsvLibGateway()
        papers = list(gateway.parse_file("empty.csv"))
        self.assertEqual(len(papers), 0)

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_parse_file_not_found(self, mock_file):
        gateway = SpringerCsvLibGateway()
        papers = list(gateway.parse_file("nonexistent.csv"))
        self.assertEqual(len(papers), 0)

if __name__ == '__main__':
    unittest.main()
