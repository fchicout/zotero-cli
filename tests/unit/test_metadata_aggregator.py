from unittest.mock import MagicMock

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


def test_candidate_with_a_different_doi_is_not_merged():
    """Issue #340: a provider that misreads a DOI returns another paper;
    its (longer) title must not win the merge."""
    from zotero_cli.core.models import ResearchPaper
    from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService

    right = ResearchPaper(
        title="Guidelines for Human-AI Interaction", abstract="", doi="10.1145/3290605.3300233"
    )
    wrong = ResearchPaper(
        title="Digitoxin metabolism by rat liver microsomes, a much longer title",
        abstract="An unrelated abstract that is much longer than the right one.",
        doi="10.1016/0006-2952(75)90101-3",
    )
    no_doi = ResearchPaper(title="Guidelines for Human-AI Interaction", abstract="Abs", doi=None)
    providers: list = []
    for paper in (right, wrong, no_doi):
        provider = MagicMock()
        provider.get_paper_metadata.return_value = paper
        providers.append(provider)

    merged = MetadataAggregatorService(providers).get_enriched_metadata(
        "https://doi.org/10.1145/3290605.3300233"
    )
    assert merged is not None
    assert merged.title == "Guidelines for Human-AI Interaction"
    assert "Digitoxin" not in (merged.abstract or "")


def test_require_doi_match_drops_candidates_without_the_queried_doi():
    """Issue #344: providers that answer a DOI query with a free-text best
    match (and no DOI) must not contribute to data written into items."""
    from zotero_cli.core.models import ResearchPaper
    from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService

    right = ResearchPaper(title="Deep learning", abstract="", doi="10.1038/nature14539")
    guess = ResearchPaper(
        title="Deep learning in something else entirely, a longer title",
        abstract="Unrelated and longer abstract.",
        doi=None,
        publication="Some Workshop",
    )
    providers: list = []
    for paper in (right, guess):
        provider = MagicMock()
        provider.get_paper_metadata.return_value = paper
        providers.append(provider)
    aggregator = MetadataAggregatorService(providers)

    strict = aggregator.get_enriched_metadata("10.1038/nature14539", require_doi_match=True)
    assert strict is not None
    assert strict.title == "Deep learning" and strict.publication != "Some Workshop"

    lenient = aggregator.get_enriched_metadata("10.1038/nature14539")
    assert lenient is not None and lenient.publication == "Some Workshop"
