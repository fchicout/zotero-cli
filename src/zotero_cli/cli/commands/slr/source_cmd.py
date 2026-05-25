import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from zotero_cli.infra.factory import GatewayFactory

console = Console()


from typing import Any

class SLRSourceCommand:
    """
    Subcommands under 'slr source' namespace for SLR Search Ingestion and organization.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="source_verb", required=True)

        # slr source init
        init_p = sub.add_parser(
            "init",
            help="Initialize SLR 4-phase directory structure",
            description="Creates a parent collection raw_<name> and the standard four sub-collections for Title/Abstract, Full Text, Quality Assessment, and Data Extraction phases."
        )
        init_p.add_argument("--name", required=True, help="Name of the paper source (e.g. acm, ieee)")

        # slr source add
        add_p = sub.add_parser(
            "add",
            help="targeted search result ingestion into a raw_ collection",
            description="Imports RIS, BibTeX, or CSV files directly into the raw_ collection. Enforces raw_ isolation and automatically maps metadata formats."
        )
        add_p.add_argument("--name", required=True, help="Name or key of the raw collection (e.g. acm)")
        add_p.add_argument("--file", required=True, help="Path to RIS, BibTeX, or CSV file to import")
        add_p.add_argument("--verbose", action="store_true", help="Print verbose details")

        # slr source list
        list_p = sub.add_parser(
            "list",
            help="Inventory active SLR sources and pipeline health",
            description="Scans and lists active raw_ collections, detailing total item count, metadata completeness, abstract presence, and PDF coverage."
        )

    @staticmethod
    def execute(gateway, args: argparse.Namespace):
        if args.source_verb == "init":
            SLRSourceCommand._handle_init(gateway, args)
        elif args.source_verb == "add":
            SLRSourceCommand._handle_add(gateway, args)
        elif args.source_verb == "list":
            SLRSourceCommand._handle_list(gateway, args)

    @staticmethod
    def _handle_init(gateway, args):
        parent_name = f"raw_{args.name}"
        parent_key = gateway.get_collection_id_by_name(parent_name)
        if not parent_key:
            parent_key = gateway.create_collection(parent_name)
            console.print(f"[bold green]✓ Created parent collection '{parent_name}' (Key: {parent_key})[/bold green]")
        else:
            console.print(f"[yellow]! Collection '{parent_name}' already exists (Key: {parent_key})[/yellow]")

        # Standard 4-phase directory structure
        phases = [
            "01_title_abstract",
            "02_full_text",
            "03_quality_assessment",
            "04_data_extraction",
        ]
        for phase in phases:
            key = gateway.create_collection(phase, parent_key=parent_key)
            console.print(f"  - Created sub-collection '[cyan]{phase}[/cyan]' (Key: {key})")

        console.print("\n[bold yellow]⚠️  Zotero Group setup guidance for collaboration:[/bold yellow]")
        console.print(
            "It is highly recommended to run this SLR in a dedicated Zotero Group library. "
            "This ensures that individual library files are isolated, and rate limits or sync "
            "conflicts are avoided between reviewers. Ensure your config.toml has the correct "
            "library_id set to the group library."
        )

    @staticmethod
    def _handle_add(gateway, args):
        target_name = args.name
        if not target_name.startswith("raw_"):
            target_name = f"raw_{target_name}"

        target_key = gateway.get_collection_id_by_name(target_name)
        if not target_key:
            console.print(f"[bold red]Error: SLR source collection '{target_name}' not found.[/bold red]")
            console.print(f"Please initialize it first: [cyan]zotero-cli slr source init --name {args.name}[/cyan]")
            sys.exit(1)

        # Strategy resolution based on file extension
        ext = os.path.splitext(args.file)[1].lower()
        strategy: Any = None

        if ext == ".bib":
            from zotero_cli.core.strategies import BibtexImportStrategy
            strategy = BibtexImportStrategy(GatewayFactory.get_bibtex_gateway())
        elif ext == ".ris":
            from zotero_cli.core.strategies import RisImportStrategy
            strategy = RisImportStrategy(GatewayFactory.get_ris_gateway())
        elif ext == ".csv":
            # Peek at header to determine source
            with open(args.file, "r", encoding="utf-8") as f:
                header = f.readline().lower()
                if "item title" in header:
                    from zotero_cli.core.strategies import SpringerCsvImportStrategy
                    strategy = SpringerCsvImportStrategy(GatewayFactory.get_springer_csv_gateway())
                elif "document title" in header:
                    from zotero_cli.core.strategies import IeeeCsvImportStrategy
                    strategy = IeeeCsvImportStrategy(GatewayFactory.get_ieee_csv_gateway())
                elif "title" in header and "doi" in header:
                    from zotero_cli.core.strategies import CanonicalCsvImportStrategy
                    strategy = CanonicalCsvImportStrategy(GatewayFactory.get_canonical_csv_gateway())
                else:
                    console.print(f"[bold red]Error: Unknown CSV format. Headers: {header}[/bold red]")
                    sys.exit(1)
        else:
            console.print(f"[bold red]Unsupported file extension: {ext}[/bold red]")
            sys.exit(1)

        console.print(f"[bold green]Ingesting '{args.file}' into SLR collection '{target_name}'...[/bold green]")
        papers = strategy.fetch_papers(args.file)

        import_service = GatewayFactory.get_import_service(force_user=getattr(args, "user", False))
        count = import_service.import_papers(papers, target_key, verbose=getattr(args, "verbose", False))
        console.print(f"[bold green]✓ Successfully imported {count} items into '{target_name}'.[/bold green]")

    @staticmethod
    def _handle_list(gateway, args):
        with console.status("[bold green]Scanning for active SLR sources..."):
            cols = gateway.get_all_collections()

        raw_cols = [c for c in cols if c.get("data", {}).get("name", "").startswith("raw_")]
        if not raw_cols:
            console.print("[yellow]No active SLR sources found. Use 'slr source init' to create one.[/yellow]")
            return

        table = Table(title="Active SLR Sources & Pipeline Health")
        table.add_column("Source Name", style="bold green")
        table.add_column("Key", style="cyan")
        table.add_column("Total Items", justify="right")
        table.add_column("Metadata Compl. %", justify="right")
        table.add_column("Has PDF", justify="right")
        table.add_column("Missing Abstract", justify="right")

        for r in raw_cols:
            name = r["data"]["name"]
            key = r["key"]
            items = list(gateway.get_items_in_collection(key))

            total = len(items)
            if total == 0:
                table.add_row(name, key, "0", "0.00%", "0", "0")
                continue

            missing_abstract = 0
            has_pdf = 0
            completeness_points = 0

            # Each item has 5 points of completeness: title, abstract, DOI/arXiv, note, and PDF
            for item in items:
                idata = item.raw_data.get("data", {})
                title = idata.get("title", "")
                abstract = idata.get("abstractNote", "")
                doi = idata.get("DOI", "")
                arxiv = ""
                extra = idata.get("extra", "")
                if "arxiv" in extra.lower() or "arxiv" in idata.get("url", "").lower():
                    arxiv = "exists"

                # Check for PDF
                children = gateway.get_item_children(item.key)
                item_has_pdf = False
                for child in children:
                    cdata = child.get("data", child)
                    if cdata.get("itemType") == "attachment" and "pdf" in cdata.get("contentType", "").lower():
                        item_has_pdf = True
                        break

                if item_has_pdf:
                    has_pdf += 1
                    completeness_points += 1

                if title:
                    completeness_points += 1
                if abstract:
                    completeness_points += 1
                else:
                    missing_abstract += 1
                if doi or arxiv:
                    completeness_points += 1

                # Check for SDB note
                has_note = False
                for child in children:
                    cdata = child.get("data", child)
                    if cdata.get("itemType") == "note" and "decision" in cdata.get("note", "").lower():
                        has_note = True
                        break
                if has_note:
                    completeness_points += 1

            compl_percent = (completeness_points / (total * 5)) * 100

            table.add_row(
                name,
                key,
                str(total),
                f"{compl_percent:.2f}%",
                f"{has_pdf}/{total}",
                str(missing_abstract)
            )

        console.print(table)
