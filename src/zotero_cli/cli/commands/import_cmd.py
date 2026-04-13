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
        file_p = sub.add_parser(
            "file",
            help="Import .bib, .ris, .csv",
            description="Bulk-imports research items from external bibliographic files (.bib, .ris, .csv) directly into a specified Zotero collection.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Importing search results from IEEE Xplore
Problem: I've downloaded a results.ris file from IEEE and I want to import all 50 papers into my "Primary Search" folder (Key: PRI_01).
Action:  zotero-cli import file "results.ris" --collection "PRI_01"
Result:  All 50 items are uploaded to Zotero and linked to that collection.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to import files with malformed syntax or missing mandatory fields (like Title). Large files may hit Zotero API rate limits.
• Safety Tips: Always verify your .bib or .ris encoding (UTF-8 preferred) to prevent character corruption.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/import_file.md
""",
        )
        file_p.add_argument("file", help="Path to input file")
        file_p.add_argument("--collection", required=True)
        file_p.add_argument("--verbose", action="store_true")

        # ArXiv
        arxiv_p = sub.add_parser(
            "arxiv",
            help="Import from ArXiv",
            description="Directly imports research papers from the arXiv repository into a Zotero collection using a powerful Domain Specific Language (DSL) query.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Automated tracking of new papers on a topic
Problem: I want to import all recent papers by "Vaswani" in the category "cs.LG" into my "Deep Learning Tracking" (Key: DL_01) folder.
Action:  zotero-cli import arxiv --query "au:Vaswani AND cat:cs.LG" --collection "DL_01" --limit 10
Result:  The CLI finds the 10 most relevant matches and imports them into Zotero.

Cognitive Safeguards
--------------------
• Common Failure Modes: Providing an invalid DSL syntax causing API errors. arXiv API rate limits can trigger failures if multiple imports run in quick succession.
• Safety Tips: Use the --limit flag wisely. arXiv search results can be vast; importing thousands may lead to library clutter and API throttling.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/import_arxiv.md
""",
        )
        arxiv_p.add_argument("--query", required=True, help="DSL Search Query")
        arxiv_p.add_argument("--file", help="Path to file containing DSL query")
        arxiv_p.add_argument("--collection", required=True)
        arxiv_p.add_argument("--limit", type=int, default=100)
        arxiv_p.add_argument("--verbose", action="store_true")

        # DOI
        doi_p = sub.add_parser(
            "doi",
            help="Import via DOI",
            description="Imports a single research item directly into a Zotero collection using its unique Digital Object Identifier (DOI).",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Adding a specific paper from a journal website
Problem: I've found a critical paper on a journal website (DOI: 10.1038/nature12373) and want to add it to my "Climate Studies" folder (Key: CLIM_01).
Action:  zotero-cli import doi "10.1038/nature12373" --collection "CLIM_01"
Result:  The item is automatically created in Zotero with its full verified metadata.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to import an invalid DOI or one not yet indexed by primary providers.
• Safety Tips: If import fails with "DOI not found", verify on doi.org. Some DOIs take a few days to propagate through major APIs.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/import_doi.md
""",
        )
        doi_p.add_argument("doi", help="Digital Object Identifier")
        doi_p.add_argument("--collection", required=True)
        doi_p.add_argument("--verbose", action="store_true")

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
        elif args.import_type == "doi":
            self._handle_doi(import_service, args)
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

    def _handle_doi(self, service, args):
        from zotero_cli.core.strategies import DoiImportStrategy

        aggregator = GatewayFactory.get_metadata_aggregator()
        strategy = DoiImportStrategy(aggregator)
        papers = strategy.fetch_papers(args.doi)
        count = service.import_papers(papers, args.collection, args.verbose)
        print(f"Imported {count} items.")

    def _handle_manual(self, service, args):
        from zotero_cli.core.models import ResearchPaper

        paper = ResearchPaper(arxiv_id=args.arxiv_id, abstract=args.abstract, title=args.title)
        service.add_manual_paper(paper, args.collection)
        print("Added.")
