import argparse
from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry

console = Console()

@CommandRegistry.register
class ListCommand(BaseCommand):
    name = "list"
    help = "List entities (collections, groups, items)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="list_type", required=True)
        
        # Collections
        sub.add_parser("collections", help="List collections")
        
        # Groups
        sub.add_parser("groups", help="List user groups")
        
        # Items
        li_p = sub.add_parser("items", help="List items in collection")
        li_p.add_argument("--collection", required=True)
        li_p.add_argument("--top-only", action="store_true", help="Fetch only top-level items (no child notes/attachments)")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        
        if args.list_type == "collections":
            self._handle_collections(gateway, args)
        elif args.list_type == "groups":
            self._handle_groups(gateway, args)
        elif args.list_type == "items":
            self._handle_items(gateway, args)

    def _handle_collections(self, gateway, args):
        cols = gateway.get_all_collections()
        table = Table(title="Zotero Collections")
        table.add_column("Name")
        table.add_column("Key", style="cyan")
        table.add_column("Items", justify="right")
        for c in cols:
            table.add_row(c['data']['name'], c['key'], str(c['meta'].get('numItems', 0)))
        console.print(table)

    def _handle_groups(self, gateway, args):
        groups = gateway.get_user_groups()
        table = Table(title="Zotero Groups")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("URL")
        for g in groups:
            gid = str(g.get('id', 'N/A'))
            name = g.get('name', 'N/A')
            url = f"https://www.zotero.org/groups/{gid}"
            table.add_row(gid, name, url)
        console.print(table)

    def _handle_items(self, gateway, args):
        col_id = gateway.get_collection_id_by_name(args.collection)
        if not col_id:
            print(f"Error: Collection '{args.collection}' not found.")
            return
            
        items = list(gateway.get_items_in_collection(col_id, top_only=getattr(args, 'top_only', False)))
        table = Table(title=f"Items in {args.collection}")
        table.add_column("Key", style="cyan")
        table.add_column("Title")
        table.add_column("Type")
        for item in items:
            table.add_row(item.key, item.title or 'Untitled', item.item_type)
        console.print(table)
        console.print(f"\n[dim]Showing {len(items)} papers.[/dim]")
