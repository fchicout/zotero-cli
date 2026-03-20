from typing import Any, Dict

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from zotero_cli.cli.tui.components import (
    create_abstract_panel,
    create_footer_panel,
    create_header_panel,
)
from zotero_cli.core.interfaces import SnowballGraphService


class SnowballReviewTUI:
    """
    TUI for reviewing candidate papers found via snowballing.
    Prioritizes candidates by graph relevance.
    """

    def __init__(self, graph_service: SnowballGraphService):
        self.graph_service = graph_service
        self.console = Console()

    def run_review_session(self):
        self.console.clear()
        self.console.print("[bold cyan]Initializing Snowballing Review Session...[/bold cyan]")

        # Fetch candidates
        with self.console.status("[bold green]Ranking candidates...[/bold green]"):
            candidates = self.graph_service.get_ranked_candidates()

        if not candidates:
            self.console.print(
                "[bold red]No pending candidates found in the discovery graph.[/bold red]"
            )
            return

        total = len(candidates)
        self.console.print(f"[bold green]Found {total} candidates to review.[/bold green]")
        try:
            self.console.input("[bold]Press Enter to start...[/bold]")
        except (EOFError, StopIteration):
            pass

        for index, candidate in enumerate(candidates):
            self.console.clear()
            self._display_candidate(candidate, index + 1, total)

            action = self._get_user_action()

            if action == "q":
                self.console.print("[bold yellow]Quitting session... Saving graph...[/bold yellow]")
                self.graph_service.save_graph()
                break
            elif action == "s":
                self.console.print("[yellow]Skipping candidate...[/yellow]")
                continue

            status = (
                SnowballGraphService.STATUS_ACCEPTED
                if action == "a"
                else SnowballGraphService.STATUS_REJECTED
            )

            self.graph_service.update_status(candidate["doi"], status)
            self.console.print(f"[bold green]Marked as {status}![/bold green]")

        self.console.print("[bold cyan]Session Complete.[/bold cyan]")

    def _display_candidate(self, candidate: Dict[str, Any], current: int, total: int):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3), Layout(name="main"), Layout(name="footer", size=3)
        )

        layout["main"].split_row(Layout(name="body", ratio=3), Layout(name="metrics", ratio=1))

        # Header
        header_text = f"Snowballing Review {current}/{total} | DOI: {candidate['doi']}"
        layout["header"].update(create_header_panel(header_text))

        # Body (Abstract)
        layout["body"].update(
            create_abstract_panel(
                candidate.get("title"),
                [],  # Authors not always present in stub
                candidate.get("year"),  # Might be None
                candidate.get("abstract"),
            )
        )

        # Metrics Panel
        metrics = Text()
        metrics.append(
            f"\nRelevance Score: {candidate.get('relevance_score', 0)}\n", style="bold magenta"
        )
        metrics.append(f"Generation: {candidate.get('generation', 1)}\n", style="cyan")

        if candidate.get("is_influential"):
            metrics.append("\n🔥 Influential Paper\n", style="bold red")

        # Connections (Seed DOIs)
        doi = candidate["doi"]
        predecessors = list(self.graph_service.graph.predecessors(doi))
        if predecessors:
            metrics.append("\nCited by:\n", style="bold yellow")
            for p in predecessors[:5]:
                metrics.append(f"- {p}\n", style="dim")
            if len(predecessors) > 5:
                metrics.append(f"... and {len(predecessors) - 5} more\n", style="dim")

        layout["metrics"].update(Panel(metrics, title="Metrics", border_style="magenta"))

        # Footer
        controls = "[A]ccept  [R]eject  [S]kip  [Q]uit"
        layout["footer"].update(create_footer_panel(controls))

        self.console.print(layout)

    def _get_user_action(self) -> str:
        try:
            choice = Prompt.ask("Action", choices=["a", "r", "s", "q"], console=self.console)
            return choice
        except (EOFError, StopIteration):
            return "q"
