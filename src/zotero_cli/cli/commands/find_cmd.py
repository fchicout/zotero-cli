import argparse
from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.arxiv_query_parser import ArxivQueryParser
from zotero_cli.infra.factory import GatewayFactory

console = Console()

@CommandRegistry.register
class FindCommand(BaseCommand):
    name = "find"
    help = "Discovery tools (arXiv search)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="find_source", required=True)
        
        # arXiv
        arxiv_f = sub.add_parser("arxiv", help="Search arXiv")
        group_f = arxiv_f.add_mutually_exclusive_group(required=True)
        group_f.add_argument("--query")
        group_f.add_argument("--file")
        arxiv_f.add_argument("--verbose", action="store_true")

    def execute(self, args: argparse.Namespace):
        if args.find_source == "arxiv":
            self._handle_arxiv(args)

    def _handle_arxiv(self, args):
        q = args.query
        if args.file:
            with open(args.file) as f: q = f.read().strip()
            
        parser = ArxivQueryParser()
        params = parser.parse(q)
        
        # Use factory to get arxiv gateway
        # ArxivLibGateway doesn't need Zotero config
        from zotero_cli.infra.arxiv_lib import ArxivLibGateway
        arxiv = ArxivLibGateway()
        
        print(f"Searching arXiv for: {params.query} (Max: {params.max_results})")
        results = list(arxiv.search(params.query, params.max_results, params.sort_by, params.sort_order))
        
        table = Table(title=f"arXiv Results: {params.query}")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Year", justify="right")
        
        for p in results:
            table.add_row(p.arxiv_id, p.title, p.year or 'N/A')
        
        console.print(table)
        console.print(f"\n[dim]Found {len(results)} items.[/dim]")
