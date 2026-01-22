import argparse

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.tag_service import TagService


@CommandRegistry.register
class TagCommand(BaseCommand):
    name = "tag"
    help = "Manage Zotero tags"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # List
        sub.add_parser("list", help="List all unique tags")

        # Add
        add_p = sub.add_parser("add", help="Add tags to an item")
        add_p.add_argument("--item", required=True, help="Item Key")
        add_p.add_argument("--tags", required=True, help="Comma-separated tags")

        # Purge
        purge_p = sub.add_parser("purge", help="Remove all tags from a collection")
        purge_p.add_argument("--collection", required=True, help="Collection name or key")
        purge_p.add_argument("--execute", action="store_true", help="Actually perform deletions")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))
        service = GatewayFactory.get_tag_service(force_user=getattr(args, "user", False))

        if args.verb == "list":
            tags = gateway.get_tags()
            for t in sorted(tags):
                print(t)
        elif args.verb == "add":
            tags = [t.strip() for t in args.tags.split(",")]
            item = gateway.get_item(args.item)
            if item and service.add_tags_to_item(args.item, item, tags):
                print(f"Added tags to {args.item}")
            else:
                print(f"Failed to add tags to {args.item}")
        elif args.verb == "purge":
            dry_run = not args.execute
            count = service.purge_tags_from_collection(args.collection, dry_run=dry_run)
            if count >= 0:
                if dry_run:
                    print(f"[yellow]DRY RUN:[/yellow] Would purge {count} tags.")
                else:
                    print(f"Purged {count} tags.")
            else:
                print("Failed to purge tags.")
