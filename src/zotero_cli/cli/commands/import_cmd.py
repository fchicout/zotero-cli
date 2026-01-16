import argparse
import os

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.arxiv_query_parser import ArxivQueryParser
from zotero_cli.infra.factory import GatewayFactory


@CommandRegistry.register
class ImportCommand(BaseCommand):
    name = "import"
    help = "Import papers from various sources"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="import_type", required=True)

        # File
        file_p = sub.add_parser("file", help="Import .bib, .ris, .csv")
        file_p.add_argument("file", help="Path to input file")
        file_p.add_argument("--collection", required=True)
        file_p.add_argument("--verbose", action="store_true")

        # ArXiv
        arxiv_p = sub.add_parser("arxiv", help="Import from ArXiv")
        arxiv_p.add_argument("--query", required=True, help="DSL Search Query")
        arxiv_p.add_argument("--file", help="Path to file containing DSL query")
        arxiv_p.add_argument("--collection", required=True)
        arxiv_p.add_argument("--limit", type=int, default=100)
        arxiv_p.add_argument("--verbose", action="store_true")

        # Manual
        man_p = sub.add_parser("manual", help="Manual metadata entry")
        man_p.add_argument("--arxiv-id", required=True)
        man_p.add_argument("--title", required=True)
        man_p.add_argument("--abstract", default="")
        man_p.add_argument("--collection", required=True)

    def execute(self, args: argparse.Namespace):
        client = GatewayFactory.get_paper_importer(force_user=getattr(args, 'user', False))

        if args.import_type == "file":
            self._handle_file(client, args)
        elif args.import_type == "arxiv":
            self._handle_arxiv(client, args)
        elif args.import_type == "manual":
            self._handle_manual(client, args)

    def _handle_file(self, client, args):
        from zotero_cli.core.strategies import (
            BibtexImportStrategy,
            IeeeCsvImportStrategy,
            RisImportStrategy,
            SpringerCsvImportStrategy,
        )

        ext = os.path.splitext(args.file)[1].lower()
        strategy = None

        if ext == '.bib':
            strategy = BibtexImportStrategy(client.bibtex_gateway)
        elif ext == '.ris':
            strategy = RisImportStrategy(client.ris_gateway)
        elif ext == '.csv':
            # Peek at header to determine source
            with open(args.file, 'r', encoding='utf-8') as f:
                header = f.readline()
                if 'Item Title' in header:
                    strategy = SpringerCsvImportStrategy(client.springer_csv_gateway)
                else:
                    strategy = IeeeCsvImportStrategy(client.ieee_csv_gateway)
        else:
            print(f"Unsupported: {ext}")
            return

        count = client.import_with_strategy(strategy, args.file, args.collection, args.verbose)
        print(f"Imported {count} items.")

    def _handle_arxiv(self, client, args):
        from zotero_cli.core.strategies import ArxivImportStrategy
        q = args.query
        if args.file:
            with open(args.file) as f:
                q = f.read().strip()

        # DSL Logic
        if ';' in q:
            p = ArxivQueryParser().parse(q)
            q, limit, sort = p.query, p.max_results, p.sort_by
        else:
            limit, sort = args.limit, "relevance"

        strategy = ArxivImportStrategy(client.arxiv_gateway)
        count = client.import_with_strategy(strategy, q, args.collection,
                                            args.verbose, limit=limit, sort_by=sort)
        print(f"Imported {count} items.")

    def _handle_manual(self, client, args):
        client.add_paper(args.arxiv_id, args.abstract, args.title, args.collection)
        print("Added.")
