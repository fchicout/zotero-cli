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

    # Mock user workflow: Press Enter to start, 'a' for the action, then the
    # decision-depth and reason prompts (Issue #211). Since there's only 1
    # candidate, the loop will exit after this.
    mock_console.return_value.input.return_value = ""
    mock_prompt.side_effect = ["a", "abstract", "Highly relevant"]

    tui.run_review_session()

    # Verify update_status was called
    mock_graph_service.update_status.assert_called_once_with(
        "10.1001/test1",
        SnowballGraphService.STATUS_ACCEPTED,
        reason="Highly relevant",
        depth="abstract",
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
    mock_prompt.side_effect = ["r", "title", ""]

    tui.run_review_session()

    mock_graph_service.update_status.assert_called_once_with(
        "10.1001/test1",
        SnowballGraphService.STATUS_REJECTED,
        reason=None,
        depth="title",
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


@patch("zotero_cli.cli.tui.snowball_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.snowball_tui.Console")
def test_snowball_tui_flags_candidate_already_in_library(mock_console, mock_prompt, mock_graph_service):
    """Issue #224: a candidate whose DOI already exists in the library
    (matched via the same normalize_doi-based approach #205 introduced)
    is flagged rather than presented identically to a genuinely new one."""
    from zotero_cli.core.zotero_item import ZoteroItem

    mock_gateway = MagicMock()
    mock_gateway.get_all_items.return_value = iter(
        [ZoteroItem(key="EXIST1", version=1, item_type="journalArticle", doi="10.1001/TEST1")]
    )

    tui = SnowballReviewTUI(mock_graph_service, gateway=mock_gateway)
    mock_console.return_value.input.return_value = ""
    mock_prompt.side_effect = ["s"]

    tui.run_review_session()

    mock_gateway.get_all_items.assert_called_once()
    candidate = mock_graph_service.get_ranked_candidates.return_value[0]
    assert candidate["already_in_library"] is True
    assert candidate["library_key"] == "EXIST1"


@patch("zotero_cli.cli.tui.snowball_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.snowball_tui.Console")
def test_snowball_tui_no_gateway_skips_duplicate_check(mock_console, mock_prompt, mock_graph_service):
    """Without a gateway configured, review still works - candidates just
    aren't flagged, rather than crashing (Issue #224)."""
    tui = SnowballReviewTUI(mock_graph_service)
    mock_console.return_value.input.return_value = ""
    mock_prompt.side_effect = ["s"]

    tui.run_review_session()

    candidate = mock_graph_service.get_ranked_candidates.return_value[0]
    assert candidate["already_in_library"] is False
