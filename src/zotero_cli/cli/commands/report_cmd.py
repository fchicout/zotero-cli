import argparse
import sys
from pathlib import Path
from typing import Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.duplicate_service import DuplicateFinder
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class ReportCommand(BaseCommand):
    name = "report"
    help = "General library analytics and metadata reports"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="report_type", required=True)

        # report duplicates
        dupe_p = sub.add_parser(
            "duplicates",
            help="Find duplicate items across collections",
            description="Identifies duplicate items that exist across multiple specified collections, facilitating library cleanup.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples
-----------------------
Scenario: Identifying overlaps between search databases
Problem: I've imported search results from IEEE (Key: IEEE_01) and Springer (Key: SPR_01) and want to see which papers are duplicates.
Action:  zotero-cli report duplicates --collections "IEEE_01,SPR_01"
Result:  The CLI displays a table showing papers that were found in both collections, including their titles and keys.
""",
        )
        dupe_p.add_argument(
            "--collections", required=True, help="Comma-separated list of collection names or keys"
        )

        # report audit
        audit_p = sub.add_parser(
            "audit",
            help="Audit collection metadata completeness",
            description="Audits a specified collection to identify missing metadata (such as missing DOIs, abstracts, titles, or PDFs).",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples
-----------------------
Scenario: Auditing collection metadata before paper submission
Problem: I want to verify that all my final selected papers have abstracts and DOIs.
Action:  zotero-cli report audit --collection "Final Selection" --verbose
Result:  A completeness report table is printed, and missing items are detailed.
""",
        )
        audit_p.add_argument("--collection", required=True, help="Collection Name or Key to validate")
        audit_p.add_argument("--verbose", action="store_true", help="Show detailed failure logs")
        audit_p.add_argument(
            "--export-missing", help="Path to export keys of missing items to a file"
        )

        # report verify-latex
        latex_p = sub.add_parser(
            "verify-latex",
            help="Verify citations in a LaTeX manuscript",
            description="Scans a LaTeX document for citations and verifies whether they exist in your active Zotero library and are screened.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples
-----------------------
Scenario: LaTeX citation verification
Problem: I want to make sure I haven't cited any papers in my LaTeX file that are missing from Zotero.
Action:  zotero-cli report verify-latex --latex "manuscript.tex"
""",
        )
        latex_p.add_argument("--latex", required=True, help="Path to the main LaTeX file to audit")

        # report stats
        stats_p = sub.add_parser(
            "stats",
            help="Show global library metrics",
            description="Gathers and displays global statistics about your Zotero library, including item types, total counts, and temporal distributions.",
        )
        stats_p.add_argument(
            "--collection", help="Filter statistics to a specific collection instead of the entire library"
        )

        # report attachments
        attach_p = sub.add_parser(
            "attachments",
            help="Analyze disk usage and missing files",
            description="Performs an audit of PDF attachments and other files in your library or a collection, detailing disk usage and identifying items missing PDFs.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        attach_p.add_argument(
            "--collection", help="Filter analysis to a specific collection"
        )
        attach_p.add_argument(
            "--output", help="Optional path to save the Markdown attachments report"
        )

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.report_type == "duplicates":
            self._handle_duplicates(gateway, args)
        elif args.report_type == "audit":
            self._handle_audit(gateway, args)
        elif args.report_type == "verify-latex":
            self._handle_verify_latex(args)
        elif args.report_type == "stats":
            self._handle_stats(gateway, args)
        elif args.report_type == "attachments":
            self._handle_attachments(gateway, args)

    def _handle_duplicates(self, gateway, args):
        service = DuplicateFinder(gateway)
        col_ids = []
        for c in args.collections.split(","):
            c = c.strip()
            cid = gateway.get_collection_id_by_name(c) or c
            col_ids.append(cid)

        dupes = service.find_duplicates(col_ids)
        if not dupes:
            console.print("[green]No duplicates found.[/green]")
            return
        table = Table(title="Duplicate Items across Collections")
        table.add_column("Title")
        table.add_column("DOI")
        table.add_column("Keys")
        for d in dupes:
            table.add_row(d["title"] or "No Title", d["doi"] or "N/A", ", ".join(d["keys"]))
        console.print(table)

    def _handle_audit(self, _gateway, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_integrity_service(force_user=force_user)
        console.print(f"[bold green]Auditing collection: {args.collection}...[/bold green]")
        report = service.audit_collection(args.collection)

        if not report:
            sys.exit(1)

        table = Table(title=f"Collection Verification: {args.collection}")
        table.add_column("Rule", style="cyan")
        table.add_column("Status", justify="right")
        table.add_column("Missing", justify="right", style="red")

        def add_row(name, items):
            status = "[green]PASS[/green]" if not items else "[red]FAIL[/red]"
            table.add_row(name, status, str(len(items)))

        add_row("DOI / arXiv ID", report.items_missing_id)
        add_row("Title", report.items_missing_title)
        add_row("Abstract", report.items_missing_abstract)
        add_row("PDF Attachment", report.items_missing_pdf)
        add_row("Screening Note", report.items_missing_note)

        console.print(table)
        console.print(f"Total items analyzed: {report.total_items}")

        has_failures = any(
            [
                report.items_missing_id,
                report.items_missing_pdf,
                report.items_missing_note,
                report.items_missing_title,
                report.items_missing_abstract,
            ]
        )

        if args.verbose and has_failures:
            console.print("\n[bold]--- Failure Details ---[/bold]")
            if report.items_missing_id:
                console.print(f"Missing ID: {', '.join([i.key for i in report.items_missing_id])}")
            if report.items_missing_pdf:
                console.print(f"Missing PDF: {', '.join([i.key for i in report.items_missing_pdf])}")
            if report.items_missing_note:
                console.print(f"Missing Note: {', '.join([i.key for i in report.items_missing_note])}")

        if args.export_missing:
            missing_keys = set()
            for item in report.items_missing_id:
                missing_keys.add(item.key)
            for item in report.items_missing_pdf:
                missing_keys.add(item.key)

            if missing_keys:
                with open(args.export_missing, "w", encoding="utf-8") as f:
                    for key in sorted(missing_keys):
                        f.write(f"{key}\n")
                console.print(
                    f"[green]Exported {len(missing_keys)} missing item keys to {args.export_missing}[/green]"
                )
            else:
                console.print("[yellow]No missing items found to export.[/yellow]")

        if has_failures:
            console.print(
                "\n[bold red]Verification FAILED.[/bold red] Some items are not submission-ready."
            )
            sys.exit(1)
        else:
            console.print("\n[bold green]Verification PASSED.[/bold green] All items are submission-ready.")

    def _handle_verify_latex(self, args):
        service = GatewayFactory.get_audit_service(force_user=getattr(args, "user", False))
        with console.status(f"[bold green]Verifying LaTeX manuscript: {args.latex}..."):
            report = service.audit_manuscript(Path(args.latex))

        console.print(f"\n[bold]SLR LaTeX Verification for:[/bold] [cyan]{args.latex}[/cyan]")
        console.print(f"Total unique citations found: {report['total_citations']}")

        if not report["items"]:
            console.print("[yellow]No citations found in the manuscript.[/yellow]")
            return

        table = Table(title="Citation Verification Results")
        table.add_column("Key", style="dim")
        table.add_column("Status")
        table.add_column("Decision")
        table.add_column("Title")

        errors = 0
        unscreened = 0

        for key, data in report["items"].items():
            status = "[green]OK[/green]"
            decision = data.get("decision", "-")

            if not data["exists"]:
                status = "[red]MISSING[/red]"
                errors += 1
            elif not data["screened"]:
                status = "[yellow]UNSCREENED[/yellow]"
                unscreened += 1

            table.add_row(
                key,
                status,
                decision or "-",
                (data.get("title") or "")[:50] + ("..." if len(data.get("title", "")) > 50 else ""),
            )

        console.print(table)

        if errors > 0 or unscreened > 0:
            console.print(
                f"\n[bold red]Verification Failed:[/bold red] {errors} missing from library, {unscreened} unscreened in SLR."
            )
            sys.exit(1)
        else:
            console.print(
                "\n[bold green]Verification Success:[/] All citations are verified and screened."
            )

    def _handle_stats(self, gateway, args):
        with console.status("[bold green]Compiling library statistics...[/bold green]"):
            if args.collection:
                col_id = gateway.get_collection_id_by_name(args.collection) or args.collection
                items = list(gateway.get_items_in_collection(col_id))
                source_name = f"Collection: {args.collection}"
            else:
                items = list(gateway.get_all_items())
                source_name = "Full Library"

        if not items:
            console.print("[yellow]No items found to generate statistics.[/yellow]")
            return

        # Group by itemType
        type_counts: Dict[str, int] = {}
        year_counts: Dict[str, int] = {}
        creators_count = 0

        for item in items:
            itype = item.item_type
            type_counts[itype] = type_counts.get(itype, 0) + 1

            # Extract year
            date_str = item.raw_data.get("data", {}).get("date", "")
            if date_str:
                # Common date formats: YYYY, YYYY-MM-DD
                year_match = Path(date_str).name[:4]
                if year_match.isdigit():
                    year_counts[year_match] = year_counts.get(year_match, 0) + 1

            creators = item.raw_data.get("data", {}).get("creators", [])
            creators_count += len(creators)

        # Output global summary
        summary = (
            f"[bold blue]Scope:[/bold blue] {source_name}\n"
            f"[bold blue]Total Items:[/bold blue] {len(items)}\n"
            f"[bold blue]Total Authors/Creators:[/bold blue] {creators_count}"
        )
        console.print(Panel(summary, title="Library Global Metrics", expand=False))

        # Output item type table
        type_table = Table(title="Distribution by Item Type")
        type_table.add_column("Item Type", style="cyan")
        type_table.add_column("Count", justify="right", style="magenta")
        type_table.add_column("Percentage", justify="right", style="green")

        for itype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percent = (count / len(items)) * 100
            type_table.add_row(itype, str(count), f"{percent:.2f}%")
        console.print(type_table)

        # Output year distribution
        if year_counts:
            year_table = Table(title="Distribution by Publication Year")
            year_table.add_column("Year", style="cyan")
            year_table.add_column("Count", justify="right", style="magenta")
            for year, count in sorted(year_counts.items(), key=lambda x: x[0]):
                year_table.add_row(year, str(count))
            console.print(year_table)

    def _handle_attachments(self, gateway, args):
        with console.status("[bold green]Analyzing library attachments and PDF space...[/bold green]"):
            if args.collection:
                col_id = gateway.get_collection_id_by_name(args.collection) or args.collection
                items = list(gateway.get_items_in_collection(col_id))
                source_name = f"Collection: {args.collection}"
            else:
                items = list(gateway.get_all_items())
                source_name = "Full Library"

        total_files = 0
        total_size_bytes = 0
        missing_pdf = []
        pdf_counts = 0
        other_attachment_counts = 0

        for item in items:
            if item.item_type == "attachment":
                total_files += 1
                size = item.raw_data.get("data", {}).get("filesize", 0)
                if isinstance(size, int):
                    total_size_bytes += size
                if "pdf" in item.raw_data.get("data", {}).get("contentType", "").lower():
                    pdf_counts += 1
                else:
                    other_attachment_counts += 1
            elif item.item_type in ["journalArticle", "thesis", "conferencePaper", "book", "report"]:
                # Check children for PDFs
                children = gateway.get_item_children(item.key)
                has_pdf = False
                for child in children:
                    data = child.get("data", child)
                    if data.get("itemType") == "attachment":
                        total_files += 1
                        size = data.get("filesize", 0)
                        if isinstance(size, int):
                            total_size_bytes += size
                        if "pdf" in data.get("contentType", "").lower():
                            has_pdf = True
                            pdf_counts += 1
                        else:
                            other_attachment_counts += 1
                if not has_pdf:
                    missing_pdf.append(item)

        size_mb = total_size_bytes / (1024 * 1024)

        summary = (
            f"[bold blue]Scope:[/bold blue] {source_name}\n"
            f"[bold blue]Total Attachments:[/bold blue] {total_files}\n"
            f"[bold blue]  - PDF Files:[/bold blue] {pdf_counts}\n"
            f"[bold blue]  - Other Files:[/bold blue] {other_attachment_counts}\n"
            f"[bold green]Total Disk Space:[/bold green] {size_mb:.2f} MB ({total_size_bytes:,} bytes)\n"
            f"[bold red]Items Missing PDF:[/bold red] {len(missing_pdf)}"
        )
        console.print(Panel(summary, title="Attachments and Disk Usage Audit", expand=False))

        if missing_pdf:
            table = Table(title="Items Missing PDF Attachments")
            table.add_column("Key", style="dim")
            table.add_column("Type", style="cyan")
            table.add_column("Title")

            # Show top 25 missing
            for item in missing_pdf[:25]:
                title_display = (item.title[:77] + "...") if len(item.title) > 80 else item.title
                table.add_row(item.key, item.item_type, title_display)
            console.print(table)
            if len(missing_pdf) > 25:
                console.print(f"[dim]... and {len(missing_pdf) - 25} more items missing PDFs.[/dim]")

        # Export if requested
        if args.output:
            md = [
                f"# Library Attachments Report ({source_name})",
                f"**Generated:** {Path(args.output).name}",
                "",
                "## Executive Summary",
                f"*   **Total Attachments found:** {total_files}",
                f"*   **PDF Attachments:** {pdf_counts}",
                f"*   **Other Attachments:** {other_attachment_counts}",
                f"*   **Total Size:** {size_mb:.2f} MB",
                f"*   **Items Missing PDFs:** {len(missing_pdf)}",
                "",
                "## Items Missing PDFs (Audit Trail)",
                "| Key | Item Type | Title |",
                "| :--- | :--- | :--- |",
            ]
            for item in missing_pdf:
                md.append(f"| {item.key} | {item.item_type} | {item.title} |")

            with open(args.output, "w", encoding="utf-8") as f:
                f.write("\n".join(md))
            console.print(f"[bold green]✓ Attachment report successfully exported to {args.output}[/bold green]")
