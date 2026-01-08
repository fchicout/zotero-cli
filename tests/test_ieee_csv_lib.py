import unittest
from unittest.mock import Mock, patch, mock_open
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
from zotero_cli.core.models import ResearchPaper
import csv

class TestIeeeCsvLibGateway(unittest.TestCase):
    @patch('zotero_cli.infra.ieee_csv_lib.csv.DictReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_success(self, mock_file, MockDictReader):
        # Setup mock CSV rows
        mock_csv_rows = [
            {
                'Document Title': 'Research on Cloud Platform Network Traffic Monitoring',
                'Authors': 'Z. Yang; Y. Jin; J. Liu',
                'Publication Title': '2025 IEEE 7th International Conference',
                'Publication Year': '2025',
                'DOI': '10.1109/CISCE64990.2025.11011130',
                'Abstract': 'The rapidly evolving cloud platforms...',
                'PDF Link': 'https://ieeexplore.ieee.org/pdf/11011130'
            },
            {
                'Document Title': 'Intelligent Cybersecurity Defense Strategies',
                'Authors': 'D. Ye; Z. Wang',
                'Publication Title': '2025 2nd International Conference',
                'Publication Year': '2025',
                'DOI': '10.1109/ASENS64990.2025.11011130',
                'Abstract': 'As the complexity of cyberattacks...',
                'PDF Link': 'https://ieeexplore.ieee.org/pdf/11011131'
            }
        ]
        MockDictReader.return_value = mock_csv_rows

        gateway = IeeeCsvLibGateway()
        papers = list(gateway.parse_file("ieee.csv"))

        self.assertEqual(len(papers), 2)
        
        self.assertIsInstance(papers[0], ResearchPaper)
        self.assertEqual(papers[0].title, "Research on Cloud Platform Network Traffic Monitoring")
        self.assertEqual(papers[0].abstract, "The rapidly evolving cloud platforms...")
        self.assertEqual(papers[0].authors, ["Z. Yang", "Y. Jin", "J. Liu"])
        self.assertEqual(papers[0].publication, "2025 IEEE 7th International Conference")
        self.assertEqual(papers[0].year, "2025")
        self.assertEqual(papers[0].doi, "10.1109/CISCE64990.2025.11011130")
        self.assertEqual(papers[0].url, "https://ieeexplore.ieee.org/pdf/11011130")

        self.assertIsInstance(papers[1], ResearchPaper)
        self.assertEqual(papers[1].title, "Intelligent Cybersecurity Defense Strategies")
        self.assertEqual(papers[1].authors, ["D. Ye", "Z. Wang"])
        self.assertEqual(papers[1].year, "2025")

    @patch('zotero_cli.infra.ieee_csv_lib.csv.DictReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_file_empty(self, mock_file, MockDictReader):
        MockDictReader.return_value = []
        gateway = IeeeCsvLibGateway()
        papers = list(gateway.parse_file("empty.csv"))
        self.assertEqual(len(papers), 0)

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_parse_file_not_found(self, mock_file):
        gateway = IeeeCsvLibGateway()
        papers = list(gateway.parse_file("nonexistent.csv"))
        self.assertEqual(len(papers), 0)

if __name__ == '__main__':
    unittest.main()
