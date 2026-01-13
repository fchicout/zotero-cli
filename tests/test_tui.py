import pytest
from unittest.mock import MagicMock, call, patch
from zotero_cli.cli.tui import TuiScreeningService
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_service():
    return MagicMock()

@pytest.fixture
def mock_console():
    with patch("zotero_cli.cli.tui.Console") as mock:
        yield mock.return_value

@pytest.fixture
def tui(mock_service, mock_console):
    tui_instance = TuiScreeningService(mock_service)
    # We need to ensure the tui uses our mock console
    tui_instance.console = mock_console 
    return tui_instance

def test_run_session_no_items(tui, mock_service, mock_console):
    # Setup
    mock_service.get_pending_items.return_value = []
    
    # Mock persona and phase input
    with patch("zotero_cli.cli.tui.Prompt.ask", side_effect=["test_persona", "title_abstract"]):
        # Execute
        tui.run_screening_session("Source", "Inc", "Exc")
    
    # Verify
    mock_service.get_pending_items.assert_called_with("Source")
    mock_console.print.assert_any_call("[bold red]No pending items found to screen.[/bold red]")

def test_run_session_quit_immediately(tui, mock_service, mock_console):
    # Setup
    items = [ZoteroItem(key="1", version=1, item_type="note", title="T1")]
    mock_service.get_pending_items.return_value = items
    
    # Mock user input: persona, phase, [Enter to start], 'q' to quit
    with patch("zotero_cli.cli.tui.Prompt.ask", side_effect=["test_persona", "title_abstract", "q"]):
        tui.run_screening_session("Source", "Inc", "Exc")
    
    # Verify
    mock_console.print.assert_any_call("[bold yellow]Quitting session...[/bold yellow]")
    # No decision should be recorded
    mock_service.record_decision.assert_not_called()

def test_run_session_skip_then_quit(tui, mock_service, mock_console):
    # Setup
    items = [
        ZoteroItem(key="1", version=1, item_type="note", title="T1"),
        ZoteroItem(key="2", version=1, item_type="note", title="T2")
    ]
    mock_service.get_pending_items.return_value = items
    
    # Mock user input: persona, phase, 's' (skip item 1), then 'q' (quit at item 2)
    with patch("zotero_cli.cli.tui.Prompt.ask", side_effect=["p", "title_abstract", "s", "q"]):
        tui.run_screening_session("Source", "Inc", "Exc")
    
    # Verify
    mock_console.print.assert_any_call("[yellow]Skipping item...[/yellow]")
    mock_service.record_decision.assert_not_called()

def test_run_session_include_item(tui, mock_service, mock_console):
    # Setup
    items = [ZoteroItem(key="1", version=1, item_type="note", title="T1")]
    mock_service.get_pending_items.return_value = items
    mock_service.record_decision.return_value = True
    
    # Mock user input: 
    # 1. Persona: 'p'
    # 2. Phase: 'title_abstract'
    # 3. Action: 'i' (Include)
    # 4. Code: 'IC2' (Custom code)
    # 5. Action: 'q' (Next item action - Quit if no more items)
    with patch("zotero_cli.cli.tui.Prompt.ask", side_effect=["p", "title_abstract", "i", "IC2", "q"]):
        tui.run_screening_session("Source", "Inc", "Exc")
    
    # Verify
    mock_service.record_decision.assert_called_once_with(
        item_key="1",
        decision="INCLUDE",
        code="IC2",
        source_collection="Source",
        target_collection="Inc",
        agent="zotero-cli-tui",
        persona="p",
        phase="title_abstract"
    )
    mock_console.print.assert_any_call("[bold green]Saved![/bold green]")

def test_run_session_exclude_item_default_code(tui, mock_service, mock_console):
    # Setup
    items = [ZoteroItem(key="1", version=1, item_type="note", title="T1")]
    mock_service.get_pending_items.return_value = items
    mock_service.record_decision.return_value = True
    
    # Mock user input: persona, phase, action 'e', code 'EC1', quit
    with patch("zotero_cli.cli.tui.Prompt.ask", side_effect=["p", "title_abstract", "e", "EC1", "q"]):
        tui.run_screening_session("Source", "Inc", "Exc")
    
    # Verify
    mock_service.record_decision.assert_called_once_with(
        item_key="1",
        decision="EXCLUDE",
        code="EC1",
        source_collection="Source",
        target_collection="Exc",
        agent="zotero-cli-tui",
        persona="p",
        phase="title_abstract"
    )

def test_run_session_record_failure(tui, mock_service, mock_console):
    # Setup
    items = [ZoteroItem(key="1", version=1, item_type="note", title="T1")]
    mock_service.get_pending_items.return_value = items
    mock_service.record_decision.return_value = False
    
    # Mock user input: persona, phase, action 'i', code 'IC1', then quit
    with patch("zotero_cli.cli.tui.Prompt.ask", side_effect=["p", "title_abstract", "i", "IC1", "q"]):
        tui.run_screening_session("Source", "Inc", "Exc")
    
    # Verify
    mock_console.print.assert_any_call("[bold red]Failed to save decision![/bold red]")
    # Ensure console.input was called to pause after failure
    mock_console.input.assert_called()
