import argparse
from rich.console import Console
from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.cli.commands.inspect_cmd import InspectCommand
from zotero_cli.cli.commands.list_cmd import ListCommand

console = Console()

@CommandRegistry.register
class ItemCommand(BaseCommand):
    name = "item"
    help = "Paper/Item operations (move, inspect, delete, etc.)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)
        
        # Inspect
        inspect_p = sub.add_parser("inspect", help=InspectCommand.help)
        InspectCommand().register_args(inspect_p)

        # Move
        move_p = sub.add_parser("move", help="Move item between collections")
        move_p.add_argument("--item-id", required=True)
        move_p.add_argument("--source", help="Source collection (optional if unambiguous)")
        move_p.add_argument("--target", required=True)

        # List (Subset of list items)
        list_p = sub.add_parser("list", help="List items in a collection")
        list_p.add_argument("--collection", help="Collection name or key")
        list_p.add_argument("--trash", action="store_true", help="List items in the trash")
        list_p.add_argument("--top-only", action="store_true", help="Only show top-level items")

        # Update
        update_p = sub.add_parser("update", help="Update item metadata")
        update_p.add_argument("key", help="Item Key")
        update_p.add_argument("--doi", help="Update DOI")
        update_p.add_argument("--title", help="Update Title")
        update_p.add_argument("--abstract", help="Update Abstract")
        update_p.add_argument("--json", help="Update using raw JSON string")
        update_p.add_argument("--version", type=int, help="Current version (auto-resolved if omitted)")

        # Delete
        delete_p = sub.add_parser("delete", help="Delete an item (moves to trash)")
        delete_p.add_argument("key", help="Item Key")
        delete_p.add_argument("--version", type=int, help="Current version (auto-resolved if omitted)")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        
        if args.verb == "inspect":
            InspectCommand().execute(args)
        elif args.verb == "move":
            self._handle_move(gateway, args)
        elif args.verb == "list":
            # Adapt args for ListCommand
            args.list_type = "items"
            ListCommand().execute(args)
        elif args.verb == "update":
            self._handle_update(gateway, args)
        elif args.verb == "delete":
            self._handle_delete(gateway, args)

    def _handle_delete(self, gateway, args):
        version = args.version
        if version is None:
            item = gateway.get_item(args.key)
            if not item:
                print(f"Error: Item {args.key} not found.")
                return
            version = item.version

        if gateway.delete_item(args.key, version):
            print(f"Deleted item {args.key} successfully.")
        else:
            print(f"Failed to delete item {args.key}.")

    def _handle_update(self, gateway, args):
        import json
        payload = {}
        if args.json:
            payload = json.loads(args.json)
        
        if args.doi: payload['DOI'] = args.doi
        if args.title: payload['title'] = args.title
        if args.abstract: payload['abstractNote'] = args.abstract

        if not payload:
            print("Error: No updates provided. Use --doi, --title, --abstract, or --json.")
            return

        version = args.version
        if version is None:
            item = gateway.get_item(args.key)
            if not item:
                print(f"Error: Item {args.key} not found.")
                return
            version = item.version

        if gateway.update_item(args.key, version, payload):
            print(f"Updated item {args.key} successfully.")
        else:
            print(f"Failed to update item {args.key}.")

    def _handle_move(self, gateway, args):
        service = CollectionService(gateway)
        if service.move_item(args.source, args.target, args.item_id):
            print(f"Moved item {args.item_id} from {args.source or 'auto'} to {args.target}.")
        else:
            print("Failed to move item.")
