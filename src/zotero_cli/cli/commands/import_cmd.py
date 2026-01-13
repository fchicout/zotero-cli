import argparse
import os
import sys
from zotero_cli.cli.commands.base import BaseCommand
from zotero_cli.cli.registry import CommandRegistry
from zotero_cli.core.services.arxiv_query_parser import ArxivQueryParser
from zotero_cli.infra.factory import GatewayFactory # Assuming we'll build this
# For now, importing from main.py's helpers if possible, or duplicating logic until Factory is ready.
# To be SOLID, we should inject dependencies.

@CommandRegistry.register
class ImportCommand(BaseCommand):
    name = "import"
    help = "Ingest papers from files or web"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="import_type", required=True)
        
        # File
        file_p = sub.add_parser("file", help="Import .bib, .ris, .csv")
        file_p.add_argument("file", help="Path to file")
        file_p.add_argument("--collection", required=True)
        file_p.add_argument("--verbose", action="store_true")
        
        # ArXiv
        arxiv_p = sub.add_parser("arxiv", help="Import from ArXiv")
        g = arxiv_p.add_mutually_exclusive_group(required=True)
        g.add_argument("--query")
        g.add_argument("--file")
        arxiv_p.add_argument("--collection", required=True)
        arxiv_p.add_argument("--limit", type=int, default=100)
        arxiv_p.add_argument("--verbose", action="store_true")

        # Manual
        man_p = sub.add_parser("manual", help="Manual entry")
        man_p.add_argument("--title", required=True)
        man_p.add_argument("--arxiv-id", required=True)
        man_p.add_argument("--abstract", required=True)
        man_p.add_argument("--collection", required=True)

    def execute(self, args: argparse.Namespace):
        # We need a proper Factory here.
        # Temporary: Import from client.py or main utils
        # Refactor Goal: Create zotero_cli.container (Dependency Injection)
        from zotero_cli.cli.main import get_common_clients 
        client = get_common_clients()

        if args.import_type == "file":
            self._handle_file(client, args)
        elif args.import_type == "arxiv":
            self._handle_arxiv(client, args)
        elif args.import_type == "manual":
            self._handle_manual(client, args)

    def _handle_file(self, client, args):
        ext = os.path.splitext(args.file)[1].lower()
        if ext == '.bib':
            count = client.import_from_bibtex(args.file, args.collection, args.verbose)
        elif ext == '.ris':
            count = client.import_from_ris(args.file, args.collection, args.verbose)
        elif ext == '.csv':
             # Simple heuristic
             with open(args.file, 'r', encoding='utf-8') as f:
                header = f.readline()
                if 'Item Title' in header: count = client.import_from_springer_csv(args.file, args.collection, args.verbose)
                else: count = client.import_from_ieee_csv(args.file, args.collection, args.verbose)
        else:
            print(f"Unsupported: {ext}")
            return
        print(f"Imported {count} items.")

    def _handle_arxiv(self, client, args):
        q = args.query
        if args.file:
            with open(args.file) as f: q = f.read().strip()
        
        # DSL Logic
        if ';' in q:
            p = ArxivQueryParser().parse(q)
            q, limit, sort = p.query, p.max_results, p.sort_by
        else:
            limit, sort = args.limit, "relevance"
            
        count = client.import_from_query(q, args.collection, limit, args.verbose, sort, "descending")
        print(f"Imported {count} items.")

    def _handle_manual(self, client, args):
        client.add_paper(args.arxiv_id, args.abstract, args.title, args.collection)
        print("Added.")
