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
        import_service = GatewayFactory.get_import_service(force_user=getattr(args, "user", False))

        if args.import_type == "file":
            self._handle_file(import_service, args)
        elif args.import_type == "arxiv":
            self._handle_arxiv(import_service, args)
        elif args.import_type == "manual":
            self._handle_manual(import_service, args)

    def _handle_file(self, service, args):
        from zotero_cli.core.strategies import (
            BibtexImportStrategy,
            CanonicalCsvImportStrategy,
            IeeeCsvImportStrategy,
            ImportStrategy,
            RisImportStrategy,
            SpringerCsvImportStrategy,
        )

        ext = os.path.splitext(args.file)[1].lower()
        strategy: ImportStrategy | None = None

        if ext == ".bib":
            strategy = BibtexImportStrategy(GatewayFactory.get_bibtex_gateway())
        elif ext == ".ris":
            strategy = RisImportStrategy(GatewayFactory.get_ris_gateway())
        elif ext == ".csv":
            # Peek at header to determine source
            with open(args.file, "r", encoding="utf-8") as f:
                header = f.readline().lower()
                if "item title" in header:
                    strategy = SpringerCsvImportStrategy(GatewayFactory.get_springer_csv_gateway())
                elif "document title" in header:
                    strategy = IeeeCsvImportStrategy(GatewayFactory.get_ieee_csv_gateway())
                elif "title" in header and "doi" in header:
                    # Assume Canonical if it has 'title' and 'doi' (Our standard)
                    strategy = CanonicalCsvImportStrategy(
                        GatewayFactory.get_canonical_csv_gateway()
                    )
                else:
                    print(f"Error: Unknown CSV format. Headers: {header}")
                    return
        else:
            print(f"Unsupported: {ext}")
            return

        papers = strategy.fetch_papers(args.file)
        count = service.import_papers(papers, args.collection, args.verbose)
        print(f"Imported {count} items.")

    def _handle_arxiv(self, service, args):
        from zotero_cli.core.strategies import ArxivImportStrategy

        q = args.query
        if args.file:
            with open(args.file) as f:
                q = f.read().strip()

        # DSL Logic
        if ";" in q:
            p = ArxivQueryParser().parse(q)
            q, limit, sort = p.query, p.max_results, p.sort_by
        else:
            limit, sort = args.limit, "relevance"

        strategy = ArxivImportStrategy(GatewayFactory.get_arxiv_gateway())
        papers = strategy.fetch_papers(q, limit=limit, sort_by=sort)
        count = service.import_papers(papers, args.collection, args.verbose)
        print(f"Imported {count} items.")

    def _handle_manual(self, service, args):
        from zotero_cli.core.models import ResearchPaper

        paper = ResearchPaper(arxiv_id=args.arxiv_id, abstract=args.abstract, title=args.title)
        service.add_manual_paper(paper, args.collection)
        print("Added.")
