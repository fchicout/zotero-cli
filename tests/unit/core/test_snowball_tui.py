from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.tui.snowball_tui import SnowballReviewTUI
from zotero_cli.core.services.snowball_graph import SnowballGraphService


@pytest.fixture
def mock_graph_service():
    service = MagicMock()
    # Mock ranked candidates
    service.get_ranked_candidates.return_value = [
        {"doi": "10.1001/test1", "title": "Test Paper 1", "relevance_score": 5, "generation": 1}
    ]
    return service


@patch("zotero_cli.cli.tui.snowball_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.snowball_tui.Console")
def test_snowball_tui_accept(mock_console, mock_prompt, mock_graph_service):
    tui = SnowballReviewTUI(mock_graph_service)

    # Mock user workflow: Press Enter to start, then 'a' for first candidate
    # Since there's only 1 candidate, the loop will exit after 'a'
    mock_console.return_value.input.return_value = ""
    mock_prompt.side_effect = ["a"]

    tui.run_review_session()

    # Verify update_status was called
    mock_graph_service.update_status.assert_called_once_with(
        "10.1001/test1", SnowballGraphService.STATUS_ACCEPTED
    )


@patch("zotero_cli.cli.tui.snowball_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.snowball_tui.Console")
def test_snowball_tui_quit(mock_console, mock_prompt, mock_graph_service):
    tui = SnowballReviewTUI(mock_graph_service)

    mock_console.return_value.input.return_value = ""
    mock_prompt.side_effect = ["q"]

    tui.run_review_session()

    # Verify save_graph was called on quit
    mock_graph_service.save_graph.assert_called_once()


@patch("zotero_cli.cli.tui.snowball_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.snowball_tui.Console")
def test_snowball_tui_reject(mock_console, mock_prompt, mock_graph_service):
    tui = SnowballReviewTUI(mock_graph_service)

    mock_console.return_value.input.return_value = ""
    mock_prompt.side_effect = ["r"]

    tui.run_review_session()

    mock_graph_service.update_status.assert_called_once_with(
        "10.1001/test1", SnowballGraphService.STATUS_REJECTED
    )


@pytest.fixture
def mock_stub_graph_service():
    """A graph with one under-hydrated backward/CrossRef-style stub candidate
    (Issue #210): generic title, no abstract."""
    service = MagicMock()
    service.graph.nodes = {
        "10.1001/stub": {"title": "Reference from 10.1001/parent", "generation": 1}
    }
    service.get_ranked_candidates.return_value = [
        {
            "doi": "10.1001/stub",
            "title": "Reference from 10.1001/parent",
            "relevance_score": 1,
            "generation": 1,
        }
    ]
    return service


@patch("zotero_cli.cli.tui.snowball_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.snowball_tui.Console")
def test_snowball_tui_hydrates_stub_candidate(mock_console, mock_prompt, mock_stub_graph_service):
    """Issue #210: a stub candidate (generic title, no abstract) is
    backfilled from the metadata service before being shown for review,
    and the enrichment is persisted back onto the graph node."""
    from zotero_cli.core.models import ResearchPaper

    mock_metadata_service = MagicMock()
    mock_metadata_service.get_enriched_metadata.return_value = ResearchPaper(
        title="The Real Title",
        abstract="A real abstract.",
        authors=["A. Researcher"],
        year="2025",
    )

    tui = SnowballReviewTUI(mock_stub_graph_service, mock_metadata_service)
    mock_console.return_value.input.return_value = ""
    mock_prompt.side_effect = ["s"]

    tui.run_review_session()

    mock_metadata_service.get_enriched_metadata.assert_called_once_with("10.1001/stub")
    node = mock_stub_graph_service.graph.nodes["10.1001/stub"]
    assert node["title"] == "The Real Title"
    assert node["abstract"] == "A real abstract."


@patch("zotero_cli.cli.tui.snowball_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.snowball_tui.Console")
def test_snowball_tui_no_metadata_service_skips_hydration(
    mock_console, mock_prompt, mock_stub_graph_service
):
    """Without a metadata service configured, review still works - it just
    shows the un-hydrated stub, rather than crashing (Issue #210)."""
    tui = SnowballReviewTUI(mock_stub_graph_service)
    mock_console.return_value.input.return_value = ""
    mock_prompt.side_effect = ["s"]

    tui.run_review_session()

    assert mock_stub_graph_service.graph.nodes["10.1001/stub"]["title"] == (
        "Reference from 10.1001/parent"
    )
