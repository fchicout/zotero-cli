import argparse

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.config import get_config
from zotero_cli.core.services.storage_service import StorageService
from zotero_cli.infra.factory import GatewayFactory


@CommandRegistry.register
class StorageCommand(BaseCommand):
    name = "storage"
    help = "Manage storage and attachments"

    def register_args(self, parser: argparse.ArgumentParser):
        subparsers = parser.add_subparsers(dest="subcommand", help="Storage subcommands")

        # checkout
        checkout_parser = subparsers.add_parser(
            "checkout",
            help="Move stored files to local storage",
            description="Moves research files (PDFs) from Zotero's internal cloud storage to your local filesystem, transforming them into 'Linked Files' to save cloud space.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Migrating a library to local storage to save cloud space
Problem: My Zotero cloud storage is full and I want to move all my PDFs to my computer's "Documents/Zotero_PDFs" folder.
Action:  zotero-cli storage checkout --limit 100
Result:  The 100 oldest stored PDFs are downloaded to your local path and their links are updated in Zotero.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting a checkout without having a local storage path defined in your config.toml.
• Safety Tips: Ensure that your local storage directory is backed up.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/storage_checkout.md
""",
        )
        checkout_parser.add_argument("--limit", type=int, default=50, help="Max items to process")
        # checkout_parser.add_argument("--sort", choices=["size", "date"], default="size", help="Sort order")

    def execute(self, args: argparse.Namespace):
        if not args.subcommand:
            print("Please specify a subcommand (e.g., checkout)")
            return

        if args.subcommand == "checkout":
            self._handle_checkout(args)

    def _handle_checkout(self, args: argparse.Namespace):
        config = get_config()
        if not config:
            print("Config not loaded.")
            return

        gateway = GatewayFactory.get_zotero_gateway(config)
        service = StorageService(config, gateway)

        print(f"Starting storage checkout (Limit: {args.limit})...")
        count = service.checkout_items(limit=args.limit)
        print(f"Checkout complete. Processed {count} items.")
