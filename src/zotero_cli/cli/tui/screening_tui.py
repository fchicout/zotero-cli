from typing import List, Optional

from rich.layout import Layout
from rich.prompt import Prompt

from zotero_cli.cli.tui.components import (
    create_abstract_panel,
    create_footer_panel,
    create_header_panel,
)
from zotero_cli.core.interfaces import ScreeningService
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup
from zotero_cli.core.zotero_item import ZoteroItem


class ScreeningTUI:
    """
    Handles the TUI interaction loop for screening papers.
    """

    def __init__(self, service: ScreeningService):
        self.service = service
        self.console = Console()

    def run_screening(
        self, items: List[ZoteroItem], agent: bool = False, persona: Optional[str] = None
    ) -> None:
        """Simple wrapper for ScreenCommand compatibility."""
        _ = agent
        _ = persona
        # This is a simplified version, the original was more complex
        # and coupled to source/target collections.
        self.console.print("[bold red]Extraction TUI: Minimal Mode[/bold red]")
        for item in items:
            self._display_item(item, 1, len(items))
            self._get_user_action()

    def _display_item(self, item: ZoteroItem, current: int, total: int) -> None:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=3)
        )

        # Header
        header_text = f"Screening Item {current}/{total} | Key: {item.key}"
        layout["header"].update(create_header_panel(header_text))

        # Body
        layout["body"].update(
            create_abstract_panel(item.title, item.authors, item.date, item.abstract)
        )

        # Footer
        controls = "[I]nclude  [E]xclude  [S]kip  [Q]uit"
        layout["footer"].update(create_footer_panel(controls))

        self.console.print(layout)

    def _get_user_action(self) -> str:
        try:
            choice = Prompt.ask("Action", choices=["i", "e", "s", "q"], console=self.console)
            return choice
        except EOFError:
            return "q"
        except StopIteration:
            return "q"

    def _get_criteria_code(self, decision: str) -> str:
        default = "IC1" if decision == "INCLUDE" else "EC1"
        try:
            code = Prompt.ask(
                f"Enter {safe_markup(decision)} Criteria Code",
                default=default,
                console=self.console,
            )
            return code
        except (EOFError, StopIteration):
            return default
