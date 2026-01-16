import argparse
from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.cli.commands.list_cmd import ListCommand

@CommandRegistry.register
class CollectionCommand(BaseCommand):
    name = "collection"
    help = "Collection/Folder management"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)
        
        # List
        list_p = sub.add_parser("list", help="List all collections")
        
        # Create
        create_p = sub.add_parser("create", help="Create a new collection")
        create_p.add_argument("name")
        create_p.add_argument("--parent", help="Parent collection name or key")
        
        # Delete
        delete_p = sub.add_parser("delete", help="Delete a collection")
        delete_p.add_argument("key", help="Collection Name or Key")
        delete_p.add_argument("--version", type=int, help="Current collection version (auto-resolved if omitted)")
        delete_p.add_argument("--recursive", action="store_true", help="Delete all items and sub-collections within this collection")

        # Rename
        rename_p = sub.add_parser("rename", help="Rename a collection")
        rename_p.add_argument("key", help="Collection Key")
        rename_p.add_argument("new_name", help="New name")
        rename_p.add_argument("--version", type=int, help="Current collection version (auto-resolved if omitted)")

        # Clean
        clean_p = sub.add_parser("clean", help="Empty a collection")
        clean_p.add_argument("--collection", required=True)
        clean_p.add_argument("--parent")
        clean_p.add_argument("--verbose", action="store_true")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        
        if args.verb == "list":
            args.list_type = "collections"
            ListCommand().execute(args)
        elif args.verb == "create":
            parent_id = None
            if args.parent:
                parent_id = gateway.get_collection_id_by_name(args.parent) or args.parent
            
            key = gateway.create_collection(args.name, parent_key=parent_id)
            if key: print(f"Created collection '{args.name}' (Key: {key})")
            else: print("Failed to create collection.")
        elif args.verb == "delete" or args.verb == "rename":
            # Resolve ID from name or key
            col_id = gateway.get_collection_id_by_name(args.key)
            if not col_id:
                col_id = args.key # Assume it was already a Key
            
            version = args.version
            if version is None:
                col = gateway.get_collection(col_id)
                if not col:
                    print(f"Error: Collection '{args.key}' not found.")
                    return
                version = col.get('version')
            
            if args.verb == "delete":
                if args.recursive:
                    print(f"[bold red]WARNING: Performing recursive deletion of collection '{args.key}' ({col_id})...[/bold red]")
                    self._handle_recursive_delete(gateway, col_id)
                
                if gateway.delete_collection(col_id, version):
                    print(f"Deleted parent collection '{args.key}' ({col_id})")
                else:
                    print(f"Failed to delete collection '{args.key}'")
        elif args.verb == "clean":
            service = CollectionService(gateway)
            count = service.empty_collection(args.collection, args.parent, args.verbose)
            print(f"Deleted {count} items.")

    def _handle_recursive_delete(self, gateway, col_id):
        """Recursively deletes sub-collections and all items within."""
        # 1. Delete items in this collection
        items = list(gateway.get_items_in_collection(col_id))
        if items:
            for item in items:
                title_snip = (item.title[:50] + '...') if item.title and len(item.title) > 50 else (item.title or "No Title")
                if gateway.delete_item(item.key, item.version):
                    print(f"  [item] Deleted: {item.key} - {title_snip}")
                else:
                    print(f"  [item] FAILED to delete: {item.key}")

        # 2. Delete sub-collections recursively
        sub_cols = gateway.get_subcollections(col_id)
        if sub_cols:
            for sub in sub_cols:
                sub_name = sub.get('data', {}).get('name', 'Unknown')
                print(f"  [coll] Entering sub-collection: {sub_name} ({sub['key']})")
                self._handle_recursive_delete(gateway, sub['key'])
                if gateway.delete_collection(sub['key'], sub['version']):
                    print(f"  [coll] Deleted sub-collection: {sub_name} ({sub['key']})")
                else:
                    print(f"  [coll] FAILED to delete sub-collection: {sub['key']}")
        
