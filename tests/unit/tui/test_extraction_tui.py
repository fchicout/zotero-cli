from unittest.mock import MagicMock, patch
import pytest
from zotero_cli.cli.tui.extraction_tui import ExtractionTUI
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_service():
    service = MagicMock()
    service.validator.load_schema.return_value = {
        "version": "1.0",
        "variables": [
            {"key": "v1", "label": "Label 1", "type": "text"},
            {"key": "v2", "label": "Label 2", "type": "boolean"}
        ]
    }
    return service

@pytest.fixture
def mock_opener():
    return MagicMock()

@pytest.fixture
def tui(mock_service, mock_opener):
    return ExtractionTUI(mock_service, mock_opener)

@patch("zotero_cli.cli.tui.extraction_tui.console")
@patch("zotero_cli.cli.tui.extraction_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.extraction_tui.Confirm.ask")
def test_run_extraction_single_item(mock_confirm, mock_prompt, mock_console, tui, mock_service, mock_opener):
    # Setup Item
    item = ZoteroItem(key="ITEM1", version=1, item_type="journalArticle", title="Test Paper", url="http://example.com")
    
    # Mock Interactions
    # 1. Open URL? -> Yes
    # 2. Variable 1 (Text) -> "Answer 1"
    # 3. Evidence V1 -> "Ev 1"
    # 4. Location V1 -> "Loc 1"
    # 5. Variable 2 (Boolean) -> Yes (handled by Confirm.ask logic below)
    # 6. Evidence V2 -> ""
    # 7. Location V2 -> ""
    # 8. Save? -> Yes
    
    mock_confirm.side_effect = [True, True, True] # Open URL, Boolean Var, Save
    mock_prompt.side_effect = ["Answer 1", "Ev 1", "Loc 1", "", ""] # Text Var, Ev, Loc, Ev, Loc

    # Execute
    tui.run_extraction([item], agent="test-agent", persona="tester")

    # Verify Opener
    mock_opener.open_file.assert_called_once_with("http://example.com")

    # Verify Save
    mock_service.save_extraction.assert_called_once()
    args = mock_service.save_extraction.call_args
    key, data, version, agent, persona = args[0]
    
    assert key == "ITEM1"
    assert version == "1.0"
    assert agent == "test-agent"
    assert persona == "tester"
    assert data["v1"]["value"] == "Answer 1"
    assert data["v1"]["evidence"] == "Ev 1"
    assert data["v2"]["value"] is True

@patch("zotero_cli.cli.tui.extraction_tui.console")
def test_run_extraction_no_schema(mock_console, tui, mock_service):
    mock_service.validator.load_schema.side_effect = Exception("Missing file")
    
    tui.run_extraction([ZoteroItem(key="1", version=1, item_type="note")])
    
    mock_console.print.assert_any_call("[bold red]Error loading schema:[/bold red] Missing file")

@patch("zotero_cli.cli.tui.extraction_tui.console")
@patch("zotero_cli.cli.tui.extraction_tui.Prompt.ask")
@patch("zotero_cli.cli.tui.extraction_tui.Confirm.ask")
def test_run_extraction_skip_save(mock_confirm, mock_prompt, mock_console, tui, mock_service):
    item = ZoteroItem(key="ITEM1", version=1, item_type="journalArticle")
    
    # Mock Interactions
    # 1. Open URL? (No URL in item, so this prompt won't happen)
    # 2. Var 1 (Text) -> "A"
    # 3. Ev/Loc -> ""
    # 4. Var 2 (Bool) -> True
    # 5. Ev/Loc -> ""
    # 6. Save? -> No
    
    mock_prompt.side_effect = ["A", "", "", "", ""]
    mock_confirm.side_effect = [True, False] # Boolean Var, Save=False

    tui.run_extraction([item])

    mock_service.save_extraction.assert_not_called()
    mock_console.print.assert_any_call("[yellow]Skipped saving.[/yellow]")
