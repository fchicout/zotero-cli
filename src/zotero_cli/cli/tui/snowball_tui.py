from typing import Any, Dict, Optional

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
from zotero_cli.core.interfaces import SnowballGraphService, ZoteroGateway
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.utils.normalization import normalize_doi


class SnowballReviewTUI:
    """
    TUI for reviewing candidate papers found via snowballing.
    Prioritizes candidates by graph relevance.
    """

    def __init__(
        self,
        graph_service: SnowballGraphService,
        metadata_service: Optional[MetadataAggregatorService] = None,
        gateway: Optional[ZoteroGateway] = None,
    ):
        self.graph_service = graph_service
        # Backfills title/abstract/authors for candidates the graph only
        # holds as a stub (Issue #210), e.g. backward/CrossRef candidates
        # whose reference list entry lacked "article-title". Optional so a
        # caller with no metadata service configured still gets the
        # un-hydrated view rather than a hard dependency.
        self.metadata_service = metadata_service
        # Flags candidates already present in the library (Issue #224) -
        # optional so a caller with no gateway configured still gets a
        # working review session, just without that annotation.
        self.gateway = gateway
        self.console = Console()

    def run_review_session(self) -> None:
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

        # Flag candidates already present in the library (Issue #224) -
        # one batched scan up front, not a per-candidate re-scan.
        library_doi_index = self._build_library_doi_index()
        for candidate in candidates:
            match_key = library_doi_index.get(normalize_doi(candidate.get("doi", "")))
            candidate["already_in_library"] = match_key is not None
            candidate["library_key"] = match_key

        total = len(candidates)
        already_count = sum(1 for c in candidates if c["already_in_library"])
        self.console.print(f"[bold green]Found {total} candidates to review.[/bold green]")
        if already_count:
            self.console.print(
                f"[yellow]{already_count} already appear to be in your library.[/yellow]"
            )
        try:
            self.console.input("[bold]Press Enter to start...[/bold]")
        except (EOFError, StopIteration):
            pass

        for index, candidate in enumerate(candidates):
            self.console.clear()
            self._maybe_hydrate(candidate)
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

            depth = self._get_decision_depth()
            reason = self._get_decision_reason(status)

            self.graph_service.update_status(candidate["doi"], status, reason=reason, depth=depth)
            self.console.print(f"[bold green]Marked as {status}![/bold green]")

        self.console.print("[bold cyan]Session Complete.[/bold cyan]")

    def _build_library_doi_index(self) -> Dict[str, str]:
        """
        Builds a normalized-DOI -> Zotero key index in one pass over the
        library (Issue #224), so `run_review_session` can flag candidates
        already present without a per-candidate rescan. Reuses the same
        normalize_doi() the #205 duplicate-detection fix established, so a
        candidate's bare DOI still matches a library item stored in
        URL-form. Returns an empty index (no flags shown) if no gateway is
        configured, rather than failing the whole review session.
        """
        if not self.gateway:
            return {}

        index: Dict[str, str] = {}
        with self.console.status("[dim]Checking library for existing items...[/dim]"):
            for item in self.gateway.get_all_items():
                if item.doi:
                    index[normalize_doi(item.doi)] = item.key
        return index

    def _needs_hydration(self, candidate: Dict[str, Any]) -> bool:
        """A backward/CrossRef candidate stub has no abstract and a title
        that's just "Reference from {parent-doi}" (Issue #210) - real
        candidates have a genuine title and, usually, an abstract."""
        title = candidate.get("title") or ""
        return not candidate.get("abstract") or not title or title.startswith("Reference from ")

    def _maybe_hydrate(self, candidate: Dict[str, Any]) -> None:
        if not self.metadata_service or not self._needs_hydration(candidate):
            return

        doi = candidate["doi"]
        with self.console.status("[dim]Fetching metadata for review...[/dim]"):
            enriched = self.metadata_service.get_enriched_metadata(doi)

        if not enriched:
            return

        if enriched.title:
            candidate["title"] = enriched.title
        if enriched.abstract:
            candidate["abstract"] = enriched.abstract
        candidate["authors"] = enriched.authors
        if enriched.year:
            candidate["year"] = enriched.year

        # Persist title/abstract back onto the graph node so re-reviewing
        # (or a later import) doesn't need to re-fetch the same metadata.
        node = self.graph_service.graph.nodes.get(doi)
        if node is not None:
            if enriched.title:
                node["title"] = enriched.title
            if enriched.abstract:
                node["abstract"] = enriched.abstract

    def _display_candidate(self, candidate: Dict[str, Any], current: int, total: int) -> None:
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
                candidate.get("authors", []),
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

        if candidate.get("already_in_library"):
            library_key = candidate.get("library_key")
            metrics.append(
                f"\n⚠ Already in library ({library_key})\n"
                if library_key
                else "\n⚠ Already in library\n",
                style="bold yellow",
            )

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

    def _get_decision_depth(self) -> Optional[str]:
        """Issue #211: how much of the paper the decision was based on -
        mirrors SDB screening's evidence-depth distinction, since a
        title-only decision carries different confidence than one made
        after reading the abstract or full text."""
        try:
            return Prompt.ask(
                "Decision based on",
                choices=["title", "abstract", "full_text"],
                default="abstract",
                console=self.console,
            )
        except (EOFError, StopIteration):
            return None

    def _get_decision_reason(self, status: str) -> Optional[str]:
        """Issue #211: free-text justification, optional (empty = none),
        mirrors ScreeningService.record_decision's reason/evidence fields."""
        try:
            reason = Prompt.ask(
                f"Reason for {status} (optional)", default="", console=self.console
            )
            return reason or None
        except (EOFError, StopIteration):
            return None
