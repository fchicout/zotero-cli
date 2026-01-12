from typing import List, Optional
import sys
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.live import Live

from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.core.zotero_item import ZoteroItem

class TuiScreeningService:
    """
    Handles the TUI interaction loop for screening papers.
    """
    def __init__(self, service: ScreeningService):
        self.service = service
        self.console = Console()

    def run_screening_session(self, source_collection: str, target_included: str, target_excluded: str):
        self.console.clear()
        self.console.print(f"[bold cyan]Initializing Screening Session...[/bold cyan]")
        self.console.print(f"Source: [yellow]{source_collection}[/yellow]")
        self.console.print(f"Target (Include): [green]{target_included}[/green]")
        self.console.print(f"Target (Exclude): [red]{target_excluded}[/red]")

        # Fetch items
        with self.console.status("[bold green]Fetching pending items...[/bold green]"):
            items = self.service.get_pending_items(source_collection)
        
        if not items:
            self.console.print("[bold red]No pending items found to screen.[/bold red]")
            return

        total = len(items)
        self.console.print(f"[bold green]Found {total} items to screen.[/bold green]")
        self.console.input("[bold]Press Enter to start...[/bold]")

        for index, item in enumerate(items):
            self.console.clear()
            self._display_item(item, index + 1, total)
            
            action = self._get_user_action()
            
            if action == 'q':
                self.console.print("[bold yellow]Quitting session...[/bold yellow]")
                break
            elif action == 's':
                self.console.print("[yellow]Skipping item...[/yellow]")
                continue
            
            decision = "INCLUDE" if action == 'i' else "EXCLUDE"
            target_col = target_included if action == 'i' else target_excluded
            code = self._get_criteria_code(decision)
            
            with self.console.status(f"[bold blue]Recording decision ({decision})...[/bold blue]"):
                success = self.service.record_decision(
                    item_key=item.key,
                    decision=decision,
                    code=code,
                    source_collection=source_collection,
                    target_collection=target_col,
                    agent="zotero-cli-tui"
                )
            
            if success:
                self.console.print(f"[bold green]Saved![/bold green]")
            else:
                self.console.print(f"[bold red]Failed to save decision![/bold red]")
                self.console.input("Press Enter to continue...")

        self.console.print("[bold cyan]Session Complete.[/bold cyan]")

    def _display_item(self, item: ZoteroItem, current: int, total: int):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )

        # Header
        header_text = f"Screening Item {current}/{total} | Key: {item.key}"
        layout["header"].update(Panel(header_text, style="white on blue"))

        # Body
        title = Text(item.title, style="bold cyan")
        meta = Text(f"\nYear: {item.date} | Authors: {', '.join(item.authors[:3])}", style="yellow")
        abstract = Text(f"\n\n{item.abstract}", style="white")
        
        body_content = Text.assemble(title, meta, abstract)
        layout["body"].update(Panel(body_content, title="Abstract", border_style="green"))

        # Footer
        controls = "[I]nclude  [E]xclude  [S]kip  [Q]uit"
        layout["footer"].update(Panel(controls, style="white on blue"))

        self.console.print(layout)

    def _get_user_action(self) -> str:
        while True:
            choice = Prompt.ask("Action", choices=["i", "e", "s", "q"], console=self.console)
            return choice

    def _get_criteria_code(self, decision: str) -> str:
        default = "IC1" if decision == "INCLUDE" else "EC1"
        code = Prompt.ask(f"Enter {decision} Criteria Code", default=default, console=self.console)
        return code
