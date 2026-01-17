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
        references=["10.1/A"],
    )

    # Provider 2 (e.g., Semantic Scholar): Good title, long abstract, more authors
    p2 = ResearchPaper(
        title="A Survey on LLMs",
        abstract="A very long and detailed abstract about Large Language Models.",
        authors=["Alice Smith", "Bob Jones", "Charlie Day"],
        year=None,
        doi="10.1000/1",
        references=["10.1/B"],
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


@pytest.mark.parametrize(
    "input_title, expected",
    [
        ("ALL CAPS TITLE", "ALL CAPS TITLE"),
        ("Normal Title", "Normal Title"),
        ("  Spaces  ", "Spaces"),
    ],
)
def test_clean_title(input_title, expected):
    service = MetadataAggregatorService([])
    assert service._clean_title(input_title) == expected


def test_merge_metadata_prefers_mixed_case_title():
    service = MetadataAggregatorService([])
    p1 = ResearchPaper(title="ALL CAPS TITLE", abstract="Short")
    p2 = ResearchPaper(title="Mixed Case Title", abstract="Short")

    merged = service._merge_metadata([p1, p2])
    assert merged.title == "Mixed Case Title"


def test_merge_metadata_prefers_longer_abstract():
    service = MetadataAggregatorService([])
    p1 = ResearchPaper(title="T", abstract="Short abstract")
    p2 = ResearchPaper(title="T", abstract="A much longer abstract that should be selected")

    merged = service._merge_metadata([p1, p2])
    assert merged.abstract == "A much longer abstract that should be selected"


def test_get_enriched_metadata_handles_provider_exceptions():
    from unittest.mock import MagicMock

    mock_bad = MagicMock()
    mock_bad.get_paper_metadata.side_effect = Exception("API Down")

    p_good = ResearchPaper(title="Success", abstract="Abs")
    mock_good = MagicMock()
    mock_good.get_paper_metadata.return_value = p_good

    aggregator = MetadataAggregatorService([mock_bad, mock_good])

    # Execute
    result = aggregator.get_enriched_metadata("10.1234/test")

    # Verify
    assert result is not None
    assert result.title == "Success"


def test_get_enriched_metadata_no_results():
    from unittest.mock import MagicMock

    mock_provider = MagicMock()
    mock_provider.get_paper_metadata.return_value = None

    aggregator = MetadataAggregatorService([mock_provider])
    assert aggregator.get_enriched_metadata("test") is None
