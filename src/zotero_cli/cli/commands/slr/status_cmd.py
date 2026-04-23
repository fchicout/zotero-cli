import argparse
from rich.console import Console
from rich.table import Table

from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.core.services.slr.status_service import SLRStatusService

console = Console()

class StatusCommand:
    """
    CLI command to display SLR progress across raw_* collections.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.description = "Displays a quantitative summary of the SLR funnel across all raw_* sources."

    @staticmethod
    def execute(args: argparse.Namespace):
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))
        service = SLRStatusService(gateway)
        
        with console.status("[bold green]Scanning SLR Hierarchy..."):
            statuses = service.get_slr_status()
            
        if not statuses:
            console.print("[yellow]No raw_* collections found in the library.[/yellow]")
            return

        table = Table(title="SLR Progress Status", show_header=True, header_style="bold magenta")
        table.add_column("Source Collection")
        table.add_column("Root", justify="right")
        table.add_column("1-T&A (Inc/Exc/Pen)")
        table.add_column("2-FT (Inc/Exc/Pen)")
        table.add_column("3-QA (Acc/Ref/Pen)")
        table.add_column("4-DE (Extracted)")

        for s in statuses:
            # Helper to format stats using correct phase IDs
            def fmt(phase_id):
                stats = s.phases.get(phase_id)
                if not stats: return "-"
                return f"[green]{stats.accepted}[/green]/[orange_red1]{stats.rejected}[/orange_red1]/[dim]{stats.pending}[/dim]"

            table.add_row(
                f"[bold cyan]{s.source_name}[/bold cyan] ({s.source_key})",
                f"[bold white]{s.total_in_root}[/bold white]",
                fmt("title_abstract"),
                fmt("full_text"),
                fmt("quality_assessment"),
                f"[bold blue]{s.phases.get('data_extraction').accepted}[/bold blue]" if s.phases.get('data_extraction') else "-"
            )

        console.print(table)
