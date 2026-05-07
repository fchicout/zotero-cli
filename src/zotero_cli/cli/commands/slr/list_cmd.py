import argparse

from rich.console import Console
from rich.table import Table

from zotero_cli.infra.factory import GatewayFactory

console = Console()


class ListCommand:
    """
    CLI command to list papers in the SLR funnel by status (pending, included, excluded).
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.description = "Lists items in the SLR funnel based on their status and phase."
        sub = parser.add_subparsers(dest="list_verb", required=True)

        # Pending
        pending_p = sub.add_parser("pending", help="List items currently pending in the SLR funnel")
        pending_p.add_argument(
            "--tree", help="Filter by root collection name or key (e.g. raw_acm)"
        )

        # Included
        included_p = sub.add_parser("included", help="List items with 'Accepted' audit notes")
        included_p.add_argument("--tree", help="Filter by root collection name or key")
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
        excluded_p.add_argument("--tree", help="Filter by root collection name or key")
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

    @staticmethod
    def execute(args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_slr_status_service(force_user=force_user)

        if args.list_verb == "pending":
            ListCommand._handle_pending(service, args)
        elif args.list_verb in ["included", "excluded"]:
            ListCommand._handle_decided(service, args)

    @staticmethod
    def _handle_pending(service, args):
        with console.status("[bold green]Scanning for pending papers..."):
            pending_items = service.get_pending_items(root_key=args.tree)

        if not pending_items:
            console.print("[bold green]No pending papers found![/bold green]")
            return

        table = Table(title="Pending SLR Items", show_header=True, header_style="bold magenta")
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

        table = Table(title=title, show_header=True, header_style="bold magenta")
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
