import argparse

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.safety import warn_default_apply
from zotero_cli.core.config import get_config
from zotero_cli.core.services.storage_service import StorageService
from zotero_cli.infra.factory import GatewayFactory


@CommandRegistry.register
class StorageCommand(BaseCommand):
    name = "storage"
    help = "Manage storage and attachments"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="subcommand", help="Storage subcommands")

        # checkout
        checkout_parser = subparsers.add_parser(
            "checkout",
            help="Move stored files to local storage",
            description="Moves research files (PDFs) from Zotero's internal cloud storage to your local filesystem, transforming them into 'Linked Files' to save cloud space.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples
--------
Scenario: Migrating a library to local storage to save cloud space
Problem: My Zotero cloud storage is full and I want to move all my PDFs to my computer's "Documents/Zotero_PDFs" folder.
Action:  zotero-cli storage checkout --limit 100 --execute
Result:  The 100 oldest stored PDFs are downloaded to your local path and their links are updated in Zotero.

Scenario: Checking what a checkout would move before running it
Problem: I want to see which files would be downloaded and relinked first.
Action:  zotero-cli storage checkout --limit 100 --dry-run
Result:  Each file's destination path is listed; nothing is downloaded or relinked.

Notes
-----
• Common Failure Modes: Attempting a checkout without having a local storage path defined in your config.toml.
• Safety Tips: Ensure that your local storage directory is backed up. Group libraries are refused by default: the linked file's local path (with your username) syncs to every member, and the files are missing for them; --allow-group-library overrides this.
• Deprecation: omitting both --dry-run and --execute still checks out immediately (for now) but prints a warning; pass --execute explicitly. This becomes preview-by-default in 4.0 (Issue #378).

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/storage_checkout.md
""",
        )
        checkout_parser.add_argument("--limit", type=int, default=50, help="Max items to process")
        checkout_parser.add_argument(
            "--allow-group-library",
            action="store_true",
            help="Check out from a group library anyway (your local path syncs to all members)",
        )
        checkout_mode = checkout_parser.add_mutually_exclusive_group()
        checkout_mode.add_argument(
            "--execute",
            action="store_true",
            help="Check out the files (default for now; see Deprecation note)",
        )
        checkout_mode.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be checked out without moving anything",
        )
        # checkout_parser.add_argument("--sort", choices=["size", "date"], default="size", help="Sort order")

    def execute(self, args: argparse.Namespace) -> None:
        if not args.subcommand:
            print("Please specify a subcommand (e.g., checkout)")
            return

        if args.subcommand == "checkout":
            self._handle_checkout(args)

    def _handle_checkout(self, args: argparse.Namespace) -> None:
        config = get_config()
        if not config:
            print("Config not loaded.")
            return

        # --user applies here too (Issue #383).
        gateway = GatewayFactory.get_zotero_gateway(config, force_user=getattr(args, "user", False))
        service = StorageService(config, gateway)

        # Issue #378: predates the preview-by-default policy, so it still
        # applies immediately without either flag - just warns instead of
        # silently keeping the old behaviour forever.
        execute = bool(getattr(args, "execute", False))
        dry_run = bool(getattr(args, "dry_run", False))
        if not execute and not dry_run:
            warn_default_apply("storage checkout")
            dry_run = False
        else:
            dry_run = not execute

        print(f"Starting storage checkout (Limit: {args.limit})...")
        count = service.checkout_items(
            limit=args.limit,
            allow_group_library=getattr(args, "allow_group_library", False),
            dry_run=dry_run,
        )
        verb = "Would process" if dry_run else "Processed"
        print(f"Checkout complete. {verb} {count} items.")
