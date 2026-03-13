from unittest.mock import MagicMock

from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.strategies import DoiImportStrategy


def test_doi_import_strategy_fetch_success():
    # Setup
    mock_aggregator = MagicMock()
    mock_paper = ResearchPaper(title="Test Paper", doi="10.1234/test", abstract="Test Abstract")
    mock_aggregator.get_enriched_metadata.return_value = mock_paper

    strategy = DoiImportStrategy(mock_aggregator)

    # Execute
    results = list(strategy.fetch_papers("10.1234/test"))

    # Verify
    assert len(results) == 1
    assert results[0].title == "Test Paper"
    assert results[0].doi == "10.1234/test"
    mock_aggregator.get_enriched_metadata.assert_called_once_with("10.1234/test")


def test_doi_import_strategy_fetch_no_result():
    # Setup
    mock_aggregator = MagicMock()
    mock_aggregator.get_enriched_metadata.return_value = None

    strategy = DoiImportStrategy(mock_aggregator)

    # Execute
    results = list(strategy.fetch_papers("10.1234/missing"))

    # Verify
    assert len(results) == 0
    mock_aggregator.get_enriched_metadata.assert_called_once_with("10.1234/missing")
