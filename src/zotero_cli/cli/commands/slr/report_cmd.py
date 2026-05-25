import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zotero_cli.core.services.audit_service import CollectionAuditor
from zotero_cli.core.services.graph_service import CitationGraphService
from zotero_cli.core.services.report_service import ReportService
from zotero_cli.core.services.snapshot_service import SnapshotService
from zotero_cli.infra.factory import GatewayFactory

console = Console()


class SLRReportCommand:
    """
    Subcommands under 'slr report' namespace for SLR funnel analytics.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="report_verb", required=True)

        # slr report status
        status_p = sub.add_parser(
            "status",
            help="Displays SLR funnel progress dashboard",
            description="Scans SLR collections to report screening progress."
        )
        status_p.add_argument("--collection", required=True, help="Collection name or key")

        # slr report prisma
        prisma_p = sub.add_parser(
            "prisma",
            help="Generate PRISMA flow diagram",
            description="Generates PRISMA flow diagram data and flowchart image for a collection."
        )
        prisma_p.add_argument("--collection", required=True, help="Collection name or key")
        prisma_p.add_argument("--output-chart", help="Path to save flowchart image (uses mmdc)")
        prisma_p.add_argument("--verbose", action="store_true", help="Verbose details")

        # slr report shift
        shift_p = sub.add_parser(
            "shift",
            help="Detect items that moved between snapshots",
            description="Compares two snapshots to identify items that shifted between collections."
        )
        shift_p.add_argument("--old", required=True, help="Path to old Snapshot JSON file")
        shift_p.add_argument("--new", required=True, help="Path to new Snapshot JSON file")

        # slr report graph
        graph_p = sub.add_parser(
            "graph",
            help="Generate citation graph",
            description="Generates citation network mapping (DOT format) across collections."
        )
        graph_p.add_argument("--collections", required=True, help="Comma-separated collection names or keys")

        # slr report snapshot
        snap_p = sub.add_parser(
            "snapshot",
            help="Create a frozen JSON audit trail snapshot of a collection",
            description="Generates a machine-readable JSON freeze snapshot of a collection including all SDB decisions."
        )
        snap_p.add_argument("--collection", required=True, help="Collection name or key")
        snap_p.add_argument("--output", required=True, help="Output JSON path")

        # slr report screening
        screen_p = sub.add_parser(
            "screening",
            help="Generate Markdown Screening Report",
            description="Generates human-readable Markdown summary of screening phase decisions."
        )
        screen_p.add_argument("--collection", required=True, help="Collection name or key")
        screen_p.add_argument("--output", required=True, help="Output Markdown path")

        # slr report exclusion-summary [NEW]
        excl_p = sub.add_parser(
            "exclusion-summary",
            help="Summarize rejection reason codes and percentages",
            description="Aggregates and reports counts and percentages for rejection reason codes across screened papers."
        )
        excl_p.add_argument("--collection", required=True, help="Collection name or key")

        # slr report consensus [NEW]
        cons_p = sub.add_parser(
            "consensus",
            help="Double-screening consensus and conflict report",
            description="Finds and highlights discrepancies/conflicts in items screened by multiple reviewers."
        )
        cons_p.add_argument("--collection", required=True, help="Collection name or key")

    @staticmethod
    def execute(gateway, args: argparse.Namespace):
        if args.report_verb == "status":
            SLRReportCommand._handle_status(gateway, args)
        elif args.report_verb == "prisma":
            SLRReportCommand._handle_prisma(gateway, args)
        elif args.report_verb == "shift":
            SLRReportCommand._handle_shift(gateway, args)
        elif args.report_verb == "graph":
            SLRReportCommand._handle_graph(gateway, args)
        elif args.report_verb == "snapshot":
            SLRReportCommand._handle_snapshot(gateway, args)
        elif args.report_verb == "screening":
            SLRReportCommand._handle_screening(gateway, args)
        elif args.report_verb == "exclusion-summary":
            SLRReportCommand._handle_exclusion_summary(gateway, args)
        elif args.report_verb == "consensus":
            SLRReportCommand._handle_consensus(gateway, args)

    @staticmethod
    def _handle_status(gateway, args):
        service = ReportService(gateway)
        with console.status("[bold green]Calculating SLR status..."):
            report = service.generate_prisma_report(args.collection)

        if not report:
            console.print(f"[bold red]Error:[/bold red] Collection '{args.collection}' not found.")
            sys.exit(1)

        from rich.progress import BarColumn, Progress, TextColumn
        console.print(f"\n[bold]SLR Funnel Status: {report.collection_name}[/bold]\n")

        percent_screened = ((report.screened_items / report.total_items * 100) if report.total_items else 0)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Screening Funnel", total=report.total_items)
            progress.update(task, completed=report.screened_items)

        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Metric")
        table.add_column("Count")
        table.add_column("Percentage")

        percent_accepted = ((report.accepted_items / report.screened_items * 100) if report.screened_items else 0)
        percent_rejected = ((report.rejected_items / report.screened_items * 100) if report.screened_items else 0)

        table.add_row("Total Funnel Items", str(report.total_items), "100%")
        table.add_row("Screened", str(report.screened_items), f"{percent_screened:.1f}%")
        table.add_row("Remaining", str(report.total_items - report.screened_items), f"{100 - percent_screened:.1f}%")
        table.add_row("Accepted (Included)", f"[green]{report.accepted_items}[/green]", f"{percent_accepted:.1f}%")
        table.add_row("Rejected (Excluded)", f"[red]{report.rejected_items}[/red]", f"{percent_rejected:.1f}%")

        console.print(table)

    @staticmethod
    def _handle_prisma(gateway, args):
        service = ReportService(gateway)
        console.print(f"Generating PRISMA report for '{args.collection}'...")
        report = service.generate_prisma_report(args.collection)

        if not report:
            console.print(f"[bold red]Error:[/bold red] Collection '{args.collection}' not found.")
            sys.exit(1)

        summary = (
            f"[bold blue]Collection:[/bold blue] {report.collection_name}\n"
            f"[bold blue]Total Items:[/bold blue] {report.total_items}\n"
            f"[bold blue]Screened:[/bold blue] {report.screened_items} "
            f"({(report.screened_items / report.total_items * 100) if report.total_items > 0 else 0:.1f}%)\n"
            f"[bold green]Accepted:[/bold green] {report.accepted_items}\n"
            f"[bold red]Rejected:[/bold red] {report.rejected_items}"
        )
        console.print(Panel(summary, title="PRISMA Screening Summary", expand=False))

        if report.rejections_by_code:
            table = Table(title="Rejection Reasons Breakdown")
            table.add_column("Code", style="cyan")
            table.add_column("Count", justify="right", style="magenta")
            table.add_column("%", justify="right", style="green")
            for code, count in sorted(report.rejections_by_code.items()):
                percent = (count / report.rejected_items * 100) if report.rejected_items > 0 else 0
                table.add_row(code, str(count), f"{percent:.1f}%")
            console.print(table)

        if args.output_chart:
            mermaid_code = service.generate_mermaid_prisma(report)
            if service.render_diagram(mermaid_code, args.output_chart):
                console.print(f"\n[bold green]✓ Flowchart saved to {args.output_chart}[/bold green]")
            else:
                console.print("\n[bold red]✗ Failed to render flowchart diagram.[/bold red]")

    @staticmethod
    def _handle_shift(gateway, args):
        service = CollectionAuditor(gateway)
        with open(args.old, "r") as f:
            old_data = json.load(f)
            snap_old = old_data.get("items", old_data) if isinstance(old_data, dict) else old_data
        with open(args.new, "r") as f:
            new_data = json.load(f)
            snap_new = new_data.get("items", new_data) if isinstance(new_data, dict) else new_data
        shifts = service.detect_shifts(snap_old, snap_new)
        if not shifts:
            console.print("[bold green]No shifts detected. State is stable.[/bold green]")
            return
        table = Table(title="Collection Shifts (Drift Detection)")
        table.add_column("Key")
        table.add_column("Title")
        table.add_column("From", style="red")
        table.add_column("To", style="green")
        for s in shifts:
            table.add_row(s["key"], s["title"][:50], ", ".join(s["from"]), ", ".join(s["to"]))
        console.print(table)

    @staticmethod
    def _handle_graph(gateway, args):
        meta_service = GatewayFactory.get_metadata_aggregator()
        service = CitationGraphService(gateway, meta_service)
        col_ids = [c.strip() for c in args.collections.split(",")]
        dot = service.build_graph(col_ids)
        console.print(dot)

    @staticmethod
    def _handle_snapshot(gateway, args):
        service = SnapshotService(gateway)
        def cli_progress(current, total, msg):
            percent = (current / total * 100) if total > 0 else 0
            sys.stdout.write(f"\r[{percent:5.1f}%] {msg:<60}")
            sys.stdout.flush()

        console.print(f"Snapshotting collection '{args.collection}'...")
        success = service.freeze_collection(args.collection, args.output, cli_progress)
        print("")
        if success:
            console.print(f"[bold green]Snapshot saved to '{args.output}'.[/bold green]")
        else:
            sys.exit(1)

    @staticmethod
    def _handle_screening(gateway, args):
        service = ReportService(gateway)
        console.print(f"Generating Markdown screening report for '{args.collection}'...")
        report = service.generate_prisma_report(args.collection)

        if not report:
            console.print(f"[bold red]Error:[/bold red] Collection '{args.collection}' not found.")
            sys.exit(1)

        md_content = service.generate_screening_markdown(report)
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(md_content)
            console.print(f"\n[bold green]✓ Screening report saved to {args.output}[/bold green]")
        except Exception as e:
            console.print(f"\n[bold red]✗ Failed to write report: {e}[/bold red]")
            sys.exit(1)

    @staticmethod
    def _handle_exclusion_summary(gateway, args):
        service = ReportService(gateway)
        with console.status("[bold green]Compiling exclusion reasons summary..."):
            report = service.generate_prisma_report(args.collection)

        if not report:
            console.print(f"[bold red]Error:[/bold red] Collection '{args.collection}' not found.")
            sys.exit(1)

        console.print(f"\n[bold]Exclusion Summary Report: {report.collection_name}[/bold]\n")
        console.print(f"Total Papers Excluded: [red]{report.rejected_items}[/red] (out of {report.screened_items} screened)")

        if not report.rejections_by_code:
            console.print("[green]No exclusion decisions found in this collection.[/green]")
            return

        table = Table(title="Exclusion Reasons Breakdown")
        table.add_column("Reason Code", style="cyan")
        table.add_column("Excluded Count", justify="right", style="magenta")
        table.add_column("Percentage", justify="right", style="green")

        for code, count in sorted(report.rejections_by_code.items(), key=lambda x: x[1], reverse=True):
            percent = (count / report.rejected_items * 100) if report.rejected_items > 0 else 0
            table.add_row(code, str(count), f"{percent:.2f}%")
        console.print(table)

    @staticmethod
    def _handle_consensus(gateway, args):
        col_id = gateway.get_collection_id_by_name(args.collection) or args.collection
        if not col_id:
            console.print(f"[bold red]Error: Collection '{args.collection}' not found.[/bold red]")
            sys.exit(1)

        items = list(gateway.get_items_in_collection(col_id))
        discrepancies = []
        agreements = 0
        total_double_screened = 0

        with console.status("[bold green]Scanning and analyzing SDB notes for reviewer consensus...[/bold green]"):
            for item in items:
                children = gateway.get_item_children(item.key)
                reviewer_decisions = {}
                for child in children:
                    data_raw = child.get("data", child)
                    if data_raw.get("itemType") == "note":
                        note = data_raw.get("note", "")
                        # Try to parse JSON from note
                        import re
                        match = re.search(r"\{.*\}", note, re.DOTALL)
                        if match:
                            try:
                                data = json.loads(match.group(0))
                                # Ensure it's an SDB screening decision note
                                if "decision" in data and "reviewer" in data:
                                    rev = data["reviewer"]
                                    dec = data["decision"].lower()
                                    reviewer_decisions[rev] = dec
                            except json.JSONDecodeError:
                                pass
                if len(reviewer_decisions) >= 2:
                    total_double_screened += 1
                    decisions_set = set(reviewer_decisions.values())
                    if len(decisions_set) > 1:
                        # Conflict!
                        discrepancies.append({
                            "key": item.key,
                            "title": item.title,
                            "decisions": reviewer_decisions
                        })
                    else:
                        agreements += 1

        summary = (
            f"[bold blue]Collection:[/bold blue] {args.collection}\n"
            f"[bold blue]Double Screened Items:[/bold blue] {total_double_screened}\n"
            f"[bold green]Consensus Agreements:[/bold green] {agreements}\n"
            f"[bold red]Discrepancy Conflicts:[/bold red] {len(discrepancies)}"
        )
        console.print(Panel(summary, title="Double Screening Consensus Report", expand=False))

        if discrepancies:
            table = Table(title="Review Discrepancies / Conflicts", show_header=True, header_style="bold red")
            table.add_column("Key", style="dim")
            table.add_column("Reviewer Decisions")
            table.add_column("Title")

            for d in discrepancies:
                dec_strings = [f"{rev}: {dec.upper()}" for rev, dec in d["decisions"].items()]
                table.add_row(d["key"], ", ".join(dec_strings), d["title"][:50] + ("..." if len(d["title"]) > 50 else ""))
            console.print(table)
        else:
            console.print("[green]Perfect consensus! No double-screening conflicts found.[/green]")
