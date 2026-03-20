import argparse

from rich.console import Console

from zotero_cli.cli.tui.factory import TUIFactory
from zotero_cli.infra.factory import GatewayFactory

console = Console()

class ScreenCommand:
    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.add_argument("--collection", help="Collection name or key to screen")
        parser.add_argument("--agent", action="store_true", help="Run in Agent-led mode")
        parser.add_argument("--persona", help="Reviewer persona (for Agent-led mode)")

    @staticmethod
    def execute(args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_screening_service(force_user=force_user)

        # 1. Resolve collection
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        col_id = None
        if args.collection:
            col_id = gateway.get_collection_id_by_name(args.collection) or args.collection

        # 2. Get items
        items = list(service.get_pending_items(str(col_id) if col_id else ""))
        if not items:
            console.print("[yellow]No pending items found for screening.[/yellow]")
            return

        # 3. Launch TUI via Factory
        tui = TUIFactory.get_screening_tui(service)
        tui.run_screening(items, agent=args.agent, persona=args.persona)
