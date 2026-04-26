import pytest

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.ris_lib import RisLibGateway


@pytest.fixture
def ris_gateway():
    return RisLibGateway()

def test_ris_parse_file(ris_gateway, tmp_path):
    ris_content = """TY  - JOUR
TI  - Test Paper
AU  - Author 1
AU  - Author 2
PY  - 2026
DO  - 10.1/1
AB  - This is an abstract.
ER  - """
    ris_file = tmp_path / "test.ris"
    ris_file.write_text(ris_content, encoding="utf-8")

    papers = list(ris_gateway.parse_file(str(ris_file)))
    assert len(papers) == 1
    assert papers[0].title == "Test Paper"
    assert papers[0].year == "2026"
    assert papers[0].doi == "10.1/1"
    assert "Author 1" in papers[0].authors

def test_ris_serialize(ris_gateway):
    paper = ResearchPaper(title="P1", authors=["A1"], year="2024", doi="10.1/2", abstract="")
    serialized = ris_gateway.serialize([paper])
    assert "TI  - P1" in serialized
    assert "AU  - A1" in serialized
    assert "PY  - 2024" in serialized

def test_ris_write_file(ris_gateway, tmp_path):
    paper = ResearchPaper(title="P2", authors=["A2"], abstract="")
    out_file = tmp_path / "out.ris"
    success = ris_gateway.write_file(str(out_file), [paper])
    assert success
    assert out_file.exists()
    assert "TI  - P2" in out_file.read_text()

def test_ris_parse_error(ris_gateway):
    # Should not crash, just return empty/print error
    papers = list(ris_gateway.parse_file("nonexistent.ris"))
    assert len(papers) == 0
