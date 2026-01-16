import pytest
import csv
from unittest.mock import Mock
from zotero_cli.core.strategies import CanonicalCsvImportStrategy
from zotero_cli.core.models import ResearchPaper

def test_canonical_csv_parsing(tmp_path):
    # Setup: Create a canonical CSV file
    csv_file = tmp_path / "canonical.csv"
    headers = ["title", "doi", "arxiv_id", "abstract", "authors", "year", "publication", "url"]
    row = {
        "title": "Test Paper",
        "doi": "10.1234/test",
        "arxiv_id": "2101.12345",
        "abstract": "This is a test abstract.",
        "authors": "Author One; Author Two",
        "year": "2024",
        "publication": "Test Journal",
        "url": "https://example.com"
    }
    
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerow(row)

    # Action
    from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway
    gateway = CanonicalCsvLibGateway()
    strategy = CanonicalCsvImportStrategy(gateway)
    papers = list(strategy.fetch_papers(str(csv_file)))

    # Assert
    assert len(papers) == 1
    p = papers[0]
    assert p.title == "Test Paper"
    assert p.doi == "10.1234/test"
    assert p.year == "2024"
    assert "Author One" in p.authors
