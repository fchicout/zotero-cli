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
    mock_graph_service.update_status.assert_called_once_with("10.1001/test1", SnowballGraphService.STATUS_ACCEPTED)

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

    mock_graph_service.update_status.assert_called_once_with("10.1001/test1", SnowballGraphService.STATUS_REJECTED)
