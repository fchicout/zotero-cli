import pytest
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService

def test_merge_logic():
    # Provider 1 (e.g., CrossRef): Good dates, DOI, short abstract
    p1 = ResearchPaper(
        title="A SURVEY ON LLMS",
        abstract="Short abstract.",
        authors=["A. Smith", "B. Jones"],
        year="2023",
        doi="10.1000/1",
        references=["10.1/A"]
    )

    # Provider 2 (e.g., Semantic Scholar): Good title, long abstract, more authors
    p2 = ResearchPaper(
        title="A Survey on LLMs",
        abstract="A very long and detailed abstract about Large Language Models.",
        authors=["Alice Smith", "Bob Jones", "Charlie Day"],
        year=None,
        doi="10.1000/1",
        references=["10.1/B"]
    )

    service = MetadataAggregatorService([])
    merged = service._merge_metadata([p1, p2])

    # Assertions
    assert merged.title == "A Survey on LLMs"
    assert merged.abstract == p2.abstract
    assert merged.authors == p2.authors
    assert merged.year == "2023"
    assert merged.doi == "10.1000/1"
    assert set(merged.references) == {"10.1/A", "10.1/B"}

@pytest.mark.parametrize("input_title, expected", [
    ("ALL CAPS TITLE", "ALL CAPS TITLE"),
    ("Normal Title", "Normal Title"),
    ("  Spaces  ", "Spaces"),
])
def test_clean_title(input_title, expected):
    service = MetadataAggregatorService([])
    assert service._clean_title(input_title) == expected