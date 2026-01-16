import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.report_service import ReportService
from zotero_cli.core.services.snapshot_service import SnapshotService

console = Console()

@CommandRegistry.register
class ReportCommand(BaseCommand):
    name = "report"
    help = "Generate reports and snapshots"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="report_type", required=True)
        
        # PRISMA
        prisma_p = sub.add_parser("prisma", help="PRISMA Statistics")
        prisma_p.add_argument("--collection", required=True)
        prisma_p.add_argument("--output-chart")
        prisma_p.add_argument("--verbose", action="store_true")
        
        # Snapshot
        snap_p = sub.add_parser("snapshot", help="JSON Audit Snapshot")
        snap_p.add_argument("--collection", required=True)
        snap_p.add_argument("--output", required=True)

        # Screening (Markdown)
        screen_p = sub.add_parser("screening", help="Generate Markdown Screening Report (PRISMA)")
        screen_p.add_argument("--collection", required=True)
        screen_p.add_argument("--output", required=True, help="Path to output Markdown file")

        # Status (Progress Dashboard)
        status_p = sub.add_parser("status", help="Show Progress Dashboard")
        status_p.add_argument("--collection", required=True)
        status_p.add_argument("--output", help="Optional path to save report (acts like screening)")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        
        if args.report_type == "prisma":
            self._handle_prisma(gateway, args)
        elif args.report_type == "snapshot":
            self._handle_snapshot(gateway, args)
        elif args.report_type == "screening":
            self._handle_screening(gateway, args)
        elif args.report_type == "status":
            self._handle_status(gateway, args)

    def _handle_prisma(self, gateway, args):
        service = ReportService(gateway)
        print(f"Generating PRISMA report for '{args.collection}'...")
        report = service.generate_prisma_report(args.collection)
        
        if not report:
            console.print(f"[bold red]Error:[/bold red] Collection '{args.collection}' not found.")
            sys.exit(1)

        summary = (
            f"[bold blue]Collection:[/bold blue] {report.collection_name}\n"
            f"[bold blue]Total Items:[/bold blue] {report.total_items}\n"
            f"[bold blue]Screened:[/bold blue] {report.screened_items} "
            f"({ (report.screened_items/report.total_items*100) if report.total_items > 0 else 0:.1f}%)\n"
            f"[bold green]Accepted:[/bold green] {report.accepted_items}\n"
            f"[bold red]Rejected:[/bold red] {report.rejected_items}"
        )
        console.print(Panel(summary, title="PRISMA Screening Summary", expand=False))
        
        if report.rejections_by_code:
            table = Table(title="Rejection Reasons")
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
                console.print(f"\n[bold green]✓ Diagram saved to {args.output_chart}[/bold green]")
            else:
                console.print(f"\n[bold red]✗ Failed to render diagram.[/bold red]")

    def _handle_snapshot(self, gateway, args):
        service = SnapshotService(gateway)
        
        def cli_progress(current, total, msg):
            percent = (current / total * 100) if total > 0 else 0
            sys.stdout.write(f"\r[{percent:5.1f}%] {msg:<60}")
            sys.stdout.flush()

        print(f"Snapshotting '{args.collection}'...")
        success = service.freeze_collection(args.collection, args.output, cli_progress)
        print("")
        if success:
            print(f"Snapshot saved to '{args.output}'.")
        else:
            sys.exit(1)

    def _handle_screening(self, gateway, args):
        service = ReportService(gateway)
        print(f"Generating Markdown screening report for '{args.collection}'...")
        report = service.generate_prisma_report(args.collection)
        
        if not report:
            console.print(f"[bold red]Error:[/bold red] Collection '{args.collection}' not found.")
            sys.exit(1)

        md_content = service.generate_screening_markdown(report)
        
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(md_content)
            console.print(f"\n[bold green]✓ Screening report saved to {args.output}[/bold green]")
        except Exception as e:
            console.print(f"\n[bold red]✗ Failed to write report: {e}[/bold red]")
            sys.exit(1)

    def _handle_status(self, gateway, args):
        if args.output:
             # Backward compatibility: if output is provided, act like screening
             return self._handle_screening(gateway, args)

        service = ReportService(gateway)
        with console.status("[bold green]Fetching items and calculating stats..."):
            report = service.generate_prisma_report(args.collection)
            
        if not report:
             console.print(f"[bold red]Error:[/bold red] Collection '{args.collection}' not found.")
             sys.exit(1)

        # Progress Bar
        from rich.progress import Progress, BarColumn, TextColumn
        
        console.print(f"\n[bold]Status Report: {report.collection_name}[/bold]\n")
        
        percent_screened = (report.screened_items / report.total_items * 100) if report.total_items else 0
        
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("{task.completed}/{task.total}"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Screening Progress", total=report.total_items)
            progress.update(task, completed=report.screened_items)
            
        # Stats Table
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Metric", style="dim")
        table.add_column("Count")
        table.add_column("Percentage")
        
        percent_accepted = (report.accepted_items / report.screened_items * 100) if report.screened_items else 0
        percent_rejected = (report.rejected_items / report.screened_items * 100) if report.screened_items else 0
        
        table.add_row("Total Items", str(report.total_items), "100%")
        table.add_row("Screened", str(report.screened_items), f"{percent_screened:.1f}%")
        table.add_row("Remaining", str(report.total_items - report.screened_items), f"{100-percent_screened:.1f}%")
        table.add_row("Accepted", f"[green]{report.accepted_items}[/green]", f"{percent_accepted:.1f}% (of screened)")
        table.add_row("Rejected", f"[red]{report.rejected_items}[/red]", f"{percent_rejected:.1f}% (of screened)")
        
        console.print(table)
