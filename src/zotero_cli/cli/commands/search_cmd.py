import argparse
from itertools import islice
from typing import Iterable

from rich.markup import escape
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.flags import add_format_flag
from zotero_cli.cli.presenters import records
from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.models import ZoteroQuery
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class SearchCommand(BaseCommand):
    name = "search"
    help = "Search for items in the Zotero library"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Performs a fast, targeted search across your Zotero library to find items matching keywords, titles, or DOIs."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Examples
--------
Scenario: Finding a paper's key for inspection
Problem: I know I have a paper about "Transformer" architectures by "Vaswani" but I don't remember its key.
Action:  zotero-cli search "Vaswani Transformer"
Result:  The CLI displays all matching papers, and I can see the key ABCD1234 for the specific paper I need.

Scenario: Feeding the hits to a script
Action:  zotero-cli search "Vaswani Transformer" --format json
Result:  A JSON list on stdout (key, title, authors, year, doi); progress messages go to stderr.

Notes
-----
• Common Failure Modes: Attempting to search for common terms without a --limit in a very large library.
• Safety Tips: Use quotes for multi-word queries. Search is case-insensitive.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/search.md
"""
        parser.add_argument(
            "query", nargs="?", help="Keyword search (matches title, creator, or year)"
        )
        parser.add_argument("--doi", help="Search by exact DOI")
        parser.add_argument("--title", help="Search by title substring")
        parser.add_argument("--limit", type=int, default=50, help="Limit results (default: 50)")
        add_format_flag(parser)

    def execute(self, args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        fmt = getattr(args, "format", "table")
        # Progress goes to stderr when stdout is carrying data.
        console = Console() if fmt == "table" else Console(stderr=True)

        if args.doi:
            console.print(f"Searching for DOI: [cyan]{escape(args.doi)}[/cyan]...")
            hits: Iterable[ZoteroItem] = gateway.get_items_by_doi(args.doi)
        elif args.title:
            console.print(f"Searching for title: [cyan]{escape(args.title)}[/cyan]...")
            hits = gateway.search_items(ZoteroQuery(q=args.title, qmode="titleCreatorYear"))
        elif args.query:
            console.print(f"Searching for: [cyan]{escape(args.query)}[/cyan]...")
            hits = gateway.search_items(ZoteroQuery(q=args.query, qmode="titleCreatorYear"))
        else:
            raise UsageError("Provide a query, --doi, or --title.")

        # Stop reading once --limit hits are in: results arrive a page at a
        # time, and every page used to be fetched first (Issue #438).
        results = list(islice(hits, args.limit) if args.limit and args.limit > 0 else hits)

        if fmt != "table":
            records.render_data(
                [
                    {
                        "key": item.key,
                        "title": item.title or "",
                        "authors": list(item.authors),
                        "year": item.date[:4] if item.date else "",
                        "doi": item.doi or "",
                    }
                    for item in results
                ],
                [
                    records.Column("key", "Key"),
                    records.Column("title", "Title"),
                    records.Column("authors", "Authors"),
                    records.Column("year", "Year"),
                    records.Column("doi", "DOI"),
                ],
                fmt,
            )
            return

        if not results:
            console.print("[yellow]No items found.[/yellow]")
            return

        table = Table(title=f"Search Results ({len(results)})")
        table.add_column("Key", style="dim")
        table.add_column("Title")
        table.add_column("Authors")
        table.add_column("Year", justify="right")
        table.add_column("DOI")

        for item in results:
            authors = ", ".join(item.authors)
            if len(authors) > 30:
                authors = authors[:27] + "..."

            title = item.title or "Unknown Title"
            display_title = title[:60] + ("..." if len(title) > 60 else "")

            table.add_row(
                item.key,
                safe_markup(display_title),
                safe_markup(authors),
                item.date[:4] if item.date else "N/A",
                item.doi or "",
            )

        console.print(table)
