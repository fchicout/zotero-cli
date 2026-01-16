from unittest.mock import mock_open, patch

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway


@patch('zotero_cli.infra.ieee_csv_lib.csv.DictReader')
@patch('builtins.open', new_callable=mock_open)
def test_parse_file_success(mock_file, MockDictReader):
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

    assert len(papers) == 2

    assert isinstance(papers[0], ResearchPaper)
    assert papers[0].title == "Research on Cloud Platform Network Traffic Monitoring"
    assert papers[0].abstract == "The rapidly evolving cloud platforms..."
    assert papers[0].authors == ["Z. Yang", "Y. Jin", "J. Liu"]
    assert papers[0].publication == "2025 IEEE 7th International Conference"
    assert papers[0].year == "2025"
    assert papers[0].doi == "10.1109/CISCE64990.2025.11011130"
    assert papers[0].url == "https://ieeexplore.ieee.org/pdf/11011130"

    assert isinstance(papers[1], ResearchPaper)
    assert papers[1].title == "Intelligent Cybersecurity Defense Strategies"
    assert papers[1].authors == ["D. Ye", "Z. Wang"]
    assert papers[1].year == "2025"

@patch('zotero_cli.infra.ieee_csv_lib.csv.DictReader')
@patch('builtins.open', new_callable=mock_open)
def test_parse_file_empty(mock_file, MockDictReader):
    MockDictReader.return_value = []
    gateway = IeeeCsvLibGateway()
    papers = list(gateway.parse_file("empty.csv"))
    assert len(papers) == 0

@patch('builtins.open', side_effect=FileNotFoundError)
def test_parse_file_not_found(mock_file):
    gateway = IeeeCsvLibGateway()
    papers = list(gateway.parse_file("nonexistent.csv"))
    assert len(papers) == 0
