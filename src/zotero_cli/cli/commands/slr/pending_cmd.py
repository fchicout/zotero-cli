import argparse

from rich.console import Console
from rich.table import Table

from zotero_cli.infra.factory import GatewayFactory

console = Console()

class PendingCommand:
    """
    CLI command to list all papers pending evaluation in the SLR funnel.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.description = "Lists all items currently pending in the SLR funnel, with reasons."
        parser.add_argument("--tree", help="Filter by root collection name or key (e.g. raw_acm)")

    @staticmethod
    def execute(args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_slr_status_service(force_user=force_user)

        with console.status("[bold green]Scanning for pending papers..."):
            pending_items = service.get_pending_items(root_key=args.tree)

        if not pending_items:
            console.print("[bold green]No pending papers found. The SLR funnel is up-to-date![/bold green]")
            return

        table = Table(title="Pending SLR Items", show_header=True, header_style="bold magenta")
        table.add_column("Key", style="dim")
        table.add_column("Phase", style="cyan")
        table.add_column("Source", style="blue")
        table.add_column("Reason", style="orange_red1")
        table.add_column("Title")

        # Group by phase for better readability
        pending_items.sort(key=lambda x: (x.phase, x.source_collection))

        for item in pending_items:
            table.add_row(
                item.item_key,
                item.phase,
                item.source_collection,
                item.reason,
                item.title[:80] + ("..." if len(item.title) > 80 else "")
            )

        console.print(table)
        console.print(f"\n[bold yellow]Total Pending Items: {len(pending_items)}[/bold yellow]")
