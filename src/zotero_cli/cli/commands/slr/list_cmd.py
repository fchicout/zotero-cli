import argparse

from rich.console import Console
from rich.table import Table

from zotero_cli.infra.factory import GatewayFactory

console = Console()

FILTER_TREE_HELP = "Filter by root collection name or key"
BOLD_MAGENTA = "bold magenta"
SCORE_REASON = "Score/Reason"



class ListCommand:
    """
    CLI command to list papers in the SLR funnel by status (pending, included, excluded).
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.description = "Lists items in the SLR funnel based on their status (pending evaluation, accepted/included, or rejected/excluded) and phase."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Scenario-Based Example (ACM Source):
------------------------------------
- List Pending: zotero-cli slr list pending --tree raw_acm
  (Identifies items awaiting data extraction)
- List Included (TA): zotero-cli slr list included --tree raw_acm --ta
  (Lists papers accepted during Title/Abstract)
- List Excluded (TA): zotero-cli slr list excluded --tree raw_acm --ta
  (Lists papers rejected during Title/Abstract with exclusion codes)

Cognitive Safeguards:
--------------------
• Note-First Truth: The included and excluded commands scan the entire tree of a source (Root + all 4 phase subfolders) to find audit notes. This ensures we see the real status regardless of where the paper is physically located.
• Phase Aliases: Supported --fullscreen as an alias for the --ft (full_text) phase.
"""
        sub = parser.add_subparsers(dest="list_verb", required=True)

        # Pending
        pending_p = sub.add_parser("pending", help="List items currently pending in the SLR funnel")
        pending_p.add_argument(
            "--tree", help="Filter by root collection name or key (e.g. raw_acm)"
        )

        # Included
        included_p = sub.add_parser("included", help="List items with 'Accepted' audit notes")
        included_p.add_argument("--tree", help=FILTER_TREE_HELP)
        included_p.add_argument(
            "--ta", action="store_true", help="Filter for Title & Abstract phase"
        )
        included_p.add_argument(
            "--fullscreen", "--ft", action="store_true", help="Filter for Full Text phase"
        )
        included_p.add_argument(
            "--qa",
            type=float,
            const=2.0,
            nargs="?",
            help="Filter for Quality Assessment phase (optional threshold)",
        )

        # Excluded
        excluded_p = sub.add_parser("excluded", help="List items with 'Rejected' audit notes")
        excluded_p.add_argument("--tree", help=FILTER_TREE_HELP)
        excluded_p.add_argument(
            "--ta", action="store_true", help="Filter for Title & Abstract phase"
        )
        excluded_p.add_argument(
            "--fullscreen", "--ft", action="store_true", help="Filter for Full Text phase"
        )
        excluded_p.add_argument(
            "--qa",
            type=float,
            const=2.0,
            nargs="?",
            help="Filter for Quality Assessment phase (optional threshold)",
        )

        # QA-Approved
        qa_p = sub.add_parser("qa-approved", help="List items approved after Quality Assessment")
        qa_p.add_argument("--tree", help=FILTER_TREE_HELP)
        qa_p.add_argument("--csv", help="Export to CSV file")
        qa_p.add_argument("--json", help="Export to JSON file")
        qa_p.add_argument("--xlsx", help="Export to XLSX file")
        qa_p.add_argument("--ods", help="Export to ODS file")

    @staticmethod
    def execute(args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_slr_status_service(force_user=force_user)

        if args.list_verb == "pending":
            ListCommand._handle_pending(service, args)
        elif args.list_verb in ["included", "excluded"]:
            ListCommand._handle_decided(service, args)
        elif args.list_verb == "qa-approved":
            ListCommand._handle_qa_approved(service, args)

    @staticmethod
    def _handle_qa_approved(service, args):
        with console.status("[bold green]Scanning for QA-approved papers..."):
            # We want items accepted at quality_assessment phase
            items = service.get_decided_items(
                "accepted", root_key=args.tree, phase_filter="quality_assessment"
            )

        if not items:
            console.print("[yellow]No QA-approved papers found.[/yellow]")
            return

        # Handle exports
        if args.csv:
            ListCommand._export_csv(items, args.csv)
        if args.json:
            ListCommand._export_json(items, args.json)
        if args.xlsx:
            ListCommand._export_xlsx(items, args.xlsx)
        if args.ods:
            ListCommand._export_ods(items, args.ods)

        # Console output if no export or alongside export
        if not (args.csv or args.json or args.xlsx or args.ods):
            table = Table(title="QA-Approved SLR Items", show_header=True, header_style=BOLD_MAGENTA)
            table.add_column("Key", style="dim")
            table.add_column("Source", style="blue")
            table.add_column("Score", style="green")
            table.add_column("Title")

            items.sort(key=lambda x: (x.source_collection, x.item_key))
            for item in items:
                title_display = (item.title[:77] + "...") if len(item.title) > 80 else item.title
                table.add_row(
                    item.item_key, item.source_collection, item.reason, title_display
                )

            console.print(table)
            console.print(f"\n[bold yellow]Total QA-Approved Items: {len(items)}[/bold yellow]")

    @staticmethod
    def _export_csv(items, filename):
        import csv

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Key", "Title", "Source", SCORE_REASON])
            for item in items:
                writer.writerow([item.item_key, item.title, item.source_collection, item.reason])
        console.print(f"[green]Successfully exported to CSV: {filename}[/green]")

    @staticmethod
    def _export_json(items, filename):
        import json

        data = [
            {
                "key": item.item_key,
                "title": item.title,
                "source": item.source_collection,
                "reason": item.reason,
            }
            for item in items
        ]
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Successfully exported to JSON: {filename}[/green]")

    @staticmethod
    def _export_xlsx(items, filename):
        try:
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = "QA-Approved"
            ws.append(["Key", "Title", "Source", SCORE_REASON])
            for item in items:
                ws.append([item.item_key, item.title, item.source_collection, item.reason])
            wb.save(filename)
            console.print(f"[green]Successfully exported to XLSX: {filename}[/green]")
        except ImportError:
            console.print("[red]Error: openpyxl not installed. Cannot export to XLSX.[/red]")

    @staticmethod
    def _export_ods(items, filename):
        try:
            from odf.opendocument import OpenDocumentSpreadsheet
            from odf.table import Table as OdfTable
            from odf.table import TableCell, TableRow
            from odf.text import P

            doc = OpenDocumentSpreadsheet()
            table = OdfTable(name="QA-Approved")
            doc.spreadsheet.addElement(table)

            # Header
            tr = TableRow()
            table.addElement(tr)
            for header in ["Key", "Title", "Source", SCORE_REASON]:
                tc = TableCell()
                tc.addElement(P(text=header))
                tr.addElement(tc)

            # Data
            for item in items:
                tr = TableRow()
                table.addElement(tr)
                for val in [item.item_key, item.title, item.source_collection, item.reason]:
                    tc = TableCell()
                    tc.addElement(P(text=str(val)))
                    tr.addElement(tc)

            doc.save(filename)
            console.print(f"[green]Successfully exported to ODS: {filename}[/green]")
        except ImportError:
            console.print(
                "[red]Error: odfpy not installed. Cannot export to ODS. Please run 'pip install odfpy'[/red]"
            )

    @staticmethod
    def _handle_pending(service, args):
        with console.status("[bold green]Scanning for pending papers..."):
            pending_items = service.get_pending_items(root_key=args.tree)

        if not pending_items:
            console.print("[bold green]No pending papers found![/bold green]")
            return

        table = Table(title="Pending SLR Items", show_header=True, header_style=BOLD_MAGENTA)
        table.add_column("Key", style="dim")
        table.add_column("Phase", style="cyan")
        table.add_column("Source", style="blue")
        table.add_column("Reason", style="orange_red1")
        table.add_column("Title")

        pending_items.sort(key=lambda x: (x.phase, x.source_collection))
        for item in pending_items:
            title_display = (item.title[:77] + "...") if len(item.title) > 80 else item.title
            table.add_row(
                item.item_key, item.phase, item.source_collection, item.reason, title_display
            )

        console.print(table)
        console.print(f"\n[bold yellow]Total Pending Items: {len(pending_items)}[/bold yellow]")

    @staticmethod
    def _handle_decided(service, args):
        decision_type = "accepted" if args.list_verb == "included" else "rejected"
        phase_filter = None
        if args.ta:
            phase_filter = "title_abstract"
        elif args.fullscreen:
            phase_filter = "full_text"
        elif args.qa is not None:
            phase_filter = "quality_assessment"

        with console.status(f"[bold green]Scanning for {decision_type} papers..."):
            items = service.get_decided_items(
                decision_type, root_key=args.tree, phase_filter=phase_filter
            )

        if not items:
            console.print(
                f"[yellow]No {decision_type} papers found for the specified filters.[/yellow]"
            )
            return

        title = f"{decision_type.capitalize()} SLR Items"
        if phase_filter:
            title += f" ({phase_filter})"

        table = Table(title=title, show_header=True, header_style=BOLD_MAGENTA)
        table.add_column("Key", style="dim")
        table.add_column("Phase", style="cyan")
        table.add_column("Source", style="blue")
        table.add_column("Criteria/Score", style="green" if decision_type == "accepted" else "red")
        table.add_column("Title")

        items.sort(key=lambda x: (x.phase, x.source_collection))
        for item in items:
            title_display = (item.title[:77] + "...") if len(item.title) > 80 else item.title
            table.add_row(
                item.item_key, item.phase, item.source_collection, item.reason, title_display
            )

        console.print(table)
        console.print(
            f"\n[bold yellow]Total {decision_type.capitalize()} Items: {len(items)}[/bold yellow]"
        )
