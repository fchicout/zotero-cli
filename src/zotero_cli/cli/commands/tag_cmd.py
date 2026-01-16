import argparse
from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.tag_service import TagService

@CommandRegistry.register
class TagCommand(BaseCommand):
    name = "tag"
    help = "Tag taxonomy management"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)
        
        # List
        list_p = sub.add_parser("list", help="List all unique tags")
        
        # Add
        add_p = sub.add_parser("add", help="Add tags to an item")
        add_p.add_argument("--item", required=True, help="Item Key")
        add_p.add_argument("--tags", required=True, help="Comma-separated tags")

        # Remove
        rem_p = sub.add_parser("remove", help="Remove tags from an item")
        rem_p.add_argument("--item", required=True, help="Item Key")
        rem_p.add_argument("--tags", required=True, help="Comma-separated tags")

        # Purge
        purge_p = sub.add_parser("purge", help="Permanently delete tags from library (multi-delete)")
        purge_p.add_argument("tags", help="Comma-separated tags")
        purge_p.add_argument("--version", type=int, help="Current library version (auto-resolved if omitted)")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        service = TagService(gateway)
        
        if args.verb == "list":
            tags = gateway.get_tags()
            for t in sorted(tags): print(t)
        elif args.verb == "add":
            tags = [t.strip() for t in args.tags.split(',')]
            service.add_tags_to_item(args.item, tags)
        elif args.verb == "remove":
            tags = [t.strip() for t in args.tags.split(',')]
            service.remove_tags_from_item(args.item, tags)
        elif args.verb == "purge":
            tags = [t.strip() for t in args.tags.split(',')]
            version = args.version
            if version is None:
                # To get the library version, we can do a no-op read
                # ZoteroHttpClient tracks this automatically in last_library_version
                # We'll just fetch all collections (fast-ish) to ensure it's fresh
                gateway.get_all_collections()
                from zotero_cli.infra.factory import GatewayFactory
                # This is a bit of a hack to get the version from the internal client
                # A cleaner way would be to expose get_library_version in gateway
                version = getattr(gateway.http, 'last_library_version', 0)

            if gateway.delete_tags(tags, version):
                print(f"Purged tags: {tags}")
            else:
                print("Failed to purge tags.")
