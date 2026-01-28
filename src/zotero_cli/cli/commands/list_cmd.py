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
        li_p.add_argument("--collection", required=False, help="Collection name or key")
        li_p.add_argument("--trash", action="store_true", help="List items in the trash")
        li_p.add_argument("--top-only", action="store_true", help="Fetch only top-level items")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))

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
            table.add_row(c["data"]["name"], c["key"], str(c["meta"].get("numItems", 0)))
        console.print(table)

    def _handle_groups(self, gateway, args):
        from zotero_cli.core.config import get_config

        config = get_config()
        if not config.user_id:
            print("Error: ZOTERO_USER_ID not configured. Cannot fetch user groups.")
            return

        groups = gateway.get_user_groups(config.user_id)
        table = Table(title="Zotero Groups")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("URL")
        for g in groups:
            gid = str(g.get("id", "N/A"))
            # Zotero API v3 structure for /users/{id}/groups:
            # [ { "id": 123, "data": { "name": "Group Name", ... }, ... }, ... ]
            name = g.get("data", {}).get("name", "N/A")
            url = f"https://www.zotero.org/groups/{gid}"
            table.add_row(gid, name, url)
        console.print(table)

    def _handle_items(self, gateway, args):
        if args.trash:
            items = list(gateway.get_trash_items())
            title = "Trash Items"
        else:
            if not args.collection:
                print("Error: --collection required for non-trash listings.")
                return
            col_id = gateway.get_collection_id_by_name(args.collection)
            if not col_id:
                col_id = args.collection  # Try Key

            items = list(
                gateway.get_items_in_collection(col_id, top_only=getattr(args, "top_only", False))
            )
            title = f"Items in {args.collection}"

        table = Table(title=title)
        table.add_column("Key", style="cyan")
        table.add_column("Title")
        table.add_column("Type")
        for item in items:
            table.add_row(item.key, item.title or "Untitled", item.item_type)
        console.print(table)
        console.print(f"\n[dim]Showing {len(items)} items.[/dim]")
