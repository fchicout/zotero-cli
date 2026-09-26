import argparse
import sys

from zotero_cli.cli.base import BaseCommand, CommandRegistry
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
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Migrating a library to local storage to save cloud space
Problem: My Zotero cloud storage is full and I want to move all my PDFs to my computer's "Documents/Zotero_PDFs" folder.
Action:  zotero-cli storage checkout --limit 100 --dry-run
         zotero-cli storage checkout --limit 100 --execute
Result:  The first lists the stored PDFs that would move; the second downloads them to your
         local path and turns them into linked files in Zotero.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting a checkout without having a local storage path defined in your config.toml.
• Safety Tips: Ensure that your local storage directory is backed up. Group libraries are refused by default: the linked file's local path (with your username) syncs to every member, and the files are missing for them; --allow-group-library overrides this.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/storage_checkout.md
""",
        )
        checkout_parser.add_argument("--limit", type=int, default=50, help="Max items to process")
        checkout_parser.add_argument(
            "--allow-group-library",
            action="store_true",
            help="Check out from a group library anyway (your local path syncs to all members)",
        )
        mode = checkout_parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="List the attachments that would move, without changing anything",
        )
        mode.add_argument(
            "--execute",
            action="store_true",
            help="Move the files (today's default; required from 4.0, which previews by default)",
        )

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

        gateway = GatewayFactory.get_zotero_gateway(config)
        service = StorageService(config, gateway)

        dry_run = getattr(args, "dry_run", False)
        if not dry_run and not getattr(args, "execute", False):
            # Issue #378: preview-by-default would break 3.x scripts, so it
            # waits for 4.0 (docs/COMPATIBILITY.md); warn until then.
            print(
                "Deprecation warning: from 4.0, `storage checkout` only previews unless you "
                "pass --execute. Add --execute to keep this behaviour, or --dry-run to preview.",
                file=sys.stderr,
            )

        print(f"Starting storage checkout (Limit: {args.limit})...")
        count = service.checkout_items(
            limit=args.limit,
            allow_group_library=getattr(args, "allow_group_library", False),
            dry_run=dry_run,
        )
        if dry_run:
            print(f"Preview only - nothing was changed. {count} items would move.")
        else:
            print(f"Checkout complete. Processed {count} items.")
