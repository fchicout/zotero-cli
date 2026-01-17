from unittest.mock import mock_open, patch

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway


@patch("zotero_cli.infra.springer_csv_lib.csv.DictReader")
@patch("builtins.open", new_callable=mock_open)
def test_parse_file_success(mock_file, MockDictReader):
    # Setup mock CSV rows
    mock_csv_rows = [
        {
            "Item Title": "CyberNER-LLM",
            "Publication Title": "Information and Communications Security",
            "Book Series Title": "",
            "Journal Volume": "",
            "Journal Issue": "",
            "Item DOI": "10.1007/978-981-95-3543-9_28",
            "Authors": "Xinzheng LiuWangqun LinZhaoyun Ding",  # Will be ignored
            "Publication Year": "2026",
            "URL": "https://link.springer.com/chapter/10.1007/978-981-95-3543-9_28",
            "Content Type": "Conference paper",
        },
        {
            "Item Title": "Generative AI revolution",
            "Publication Title": "",
            "Book Series Title": "Artificial Intelligence Review",
            "Journal Volume": "",
            "Journal Issue": "",
            "Item DOI": "10.1007/s10462-025-11219-5",
            "Authors": "Mueen UddinMuhammad Saad Irshad",  # Will be ignored
            "Publication Year": "2025",
            "URL": "https://link.springer.com/article/10.1007/s10462-025-11219-5",
            "Content Type": "Article",
        },
    ]
    MockDictReader.return_value = mock_csv_rows

    gateway = SpringerCsvLibGateway()
    papers = list(gateway.parse_file("test.csv"))

    assert len(papers) == 2

    assert isinstance(papers[0], ResearchPaper)
    assert papers[0].title == "CyberNER-LLM"
    assert papers[0].abstract == ""
    assert papers[0].authors == []
    assert papers[0].publication == "Information and Communications Security"
    assert papers[0].year == "2026"
    assert papers[0].doi == "10.1007/978-981-95-3543-9_28"
    assert papers[0].url == "https://link.springer.com/chapter/10.1007/978-981-95-3543-9_28"

    assert isinstance(papers[1], ResearchPaper)
    assert papers[1].title == "Generative AI revolution"
    assert papers[1].publication == "Artificial Intelligence Review"
    assert papers[1].year == "2025"
    assert papers[1].doi == "10.1007/s10462-025-11219-5"
    assert papers[1].authors == []


@patch("zotero_cli.infra.springer_csv_lib.csv.DictReader")
@patch("builtins.open", new_callable=mock_open)
def test_parse_file_empty(mock_file, MockDictReader):
    MockDictReader.return_value = []
    gateway = SpringerCsvLibGateway()
    papers = list(gateway.parse_file("empty.csv"))
    assert len(papers) == 0


@patch("builtins.open", side_effect=FileNotFoundError)
def test_parse_file_not_found(mock_file):
    gateway = SpringerCsvLibGateway()
    papers = list(gateway.parse_file("nonexistent.csv"))
    assert len(papers) == 0
