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
        checkout_parser = subparsers.add_parser("checkout", help="Move stored files to local storage")
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
