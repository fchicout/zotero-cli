import argparse

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.models import ZoteroQuery
from zotero_cli.infra.factory import GatewayFactory

console = Console()

@CommandRegistry.register
class SearchCommand(BaseCommand):
    name = "search"
    help = "Search for items in the Zotero library"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.add_argument("query", nargs="?", help="Keyword search (matches title, creator, or year)")
        parser.add_argument("--doi", help="Search by exact DOI")
        parser.add_argument("--title", help="Search by title substring")
        parser.add_argument("--limit", type=int, default=50, help="Limit results (default: 50)")

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        results = []

        if args.doi:
            console.print(f"Searching for DOI: [cyan]{args.doi}[/cyan]...")
            results = list(gateway.get_items_by_doi(args.doi))
        elif args.title:
            console.print(f"Searching for title: [cyan]{args.title}[/cyan]...")
            query = ZoteroQuery(q=args.title, qmode="titleCreatorYear")
            results = list(gateway.search_items(query))
        elif args.query:
            console.print(f"Searching for: [cyan]{args.query}[/cyan]...")
            query = ZoteroQuery(q=args.query, qmode="titleCreatorYear")
            results = list(gateway.search_items(query))
        else:
            console.print("[red]Error: Provide a query, --doi, or --title.[/red]")
            return

        if not results:
            console.print("[yellow]No items found.[/yellow]")
            return

        # Apply limit if necessary (though Zotero API already paginates)
        if args.limit and len(results) > args.limit:
            results = results[:args.limit]

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
                display_title,
                authors,
                item.date[:4] if item.date else "N/A",
                item.doi or "",
            )

        console.print(table)
