import argparse
import sys
from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.tag_service import TagService
from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.services.duplicate_service import DuplicateFinder
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.services.migration_service import MigrationService
from zotero_cli.core.services.sync_service import SyncService

console = Console()

@CommandRegistry.register
class ManageCommand(BaseCommand):
    name = "manage"
    help = "Library Maintenance (tags, pdfs, duplicates, etc.)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="manage_type", required=True)
        
        # Tags
        tag_p = sub.add_parser("tags", help="Tag operations")
        tag_p.add_argument("action", choices=["list", "rename", "delete", "add", "remove"])
        tag_p.add_argument("--tag")
        tag_p.add_argument("--old")
        tag_p.add_argument("--new")
        tag_p.add_argument("--item")
        tag_p.add_argument("--tags")
        
        # PDFs
        pdf_p = sub.add_parser("pdfs", help="PDF operations")
        pdf_p.add_argument("action", choices=["fetch", "strip"])
        pdf_p.add_argument("--collection", required=True)
        pdf_p.add_argument("--verbose", action="store_true")
        
        # Duplicates
        dup_p = sub.add_parser("duplicates", help="Find duplicates")
        dup_p.add_argument("--collections", required=True)
        
        # Move
        move_p = sub.add_parser("move", help="Move item")
        move_p.add_argument("--item-id", required=True)
        move_p.add_argument("--source", required=True)
        move_p.add_argument("--target", required=True)
        
        # Clean
        clean_p = sub.add_parser("clean", help="Empty a collection")
        clean_p.add_argument("--collection", required=True)
        clean_p.add_argument("--parent")
        clean_p.add_argument("--verbose", action="store_true")
        
        # Migrate
        mig_p = sub.add_parser("migrate", help="Migrate audit notes")
        mig_p.add_argument("--collection", required=True)
        mig_p.add_argument("--dry-run", action="store_true")

        # Sync-CSV
        sync_p = sub.add_parser("sync-csv", help="Recover local CSV from Zotero notes")
        sync_p.add_argument("--collection", required=True)
        sync_p.add_argument("--output", required=True)

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        
        if args.manage_type == "tags":
            self._handle_tags(gateway, args)
        elif args.manage_type == "pdfs":
            self._handle_pdfs(gateway, args)
        elif args.manage_type == "duplicates":
            self._handle_duplicates(gateway, args)
        elif args.manage_type == "move":
            self._handle_move(gateway, args)
        elif args.manage_type == "clean":
            self._handle_clean(gateway, args)
        elif args.manage_type == "migrate":
            self._handle_migrate(gateway, args)
        elif args.manage_type == "sync-csv":
            self._handle_sync_csv(gateway, args)

    def _handle_tags(self, gateway, args):
        service = TagService(gateway)
        if args.action == "list":
            tags = service.list_tags()
            for t in sorted(tags): print(t)
        elif args.action == "rename":
            if not args.old or not args.new:
                print("Error: --old and --new required.")
                return
            service.rename_tag(args.old, args.new)
        elif args.action == "delete":
            if not args.tag:
                print("Error: --tag required.")
                return
            service.delete_tag(args.tag)
        elif args.action == "add":
            if not args.item or not args.tags:
                print("Error: --item and --tags required.")
                return
            tags = [t.strip() for t in args.tags.split(',')]
            service.add_tags_to_item(args.item, tags)
        elif args.action == "remove":
            if not args.item or not args.tags:
                print("Error: --item and --tags required.")
                return
            tags = [t.strip() for t in args.tags.split(',')]
            service.remove_tags_from_item(args.item, tags)

    def _handle_pdfs(self, gateway, args):
        from zotero_cli.infra.factory import GatewayFactory
        service = GatewayFactory.get_attachment_service(force_user=getattr(args, 'user', False))
        if args.action == "fetch":
            from zotero_cli.infra.factory import GatewayFactory
            importer = GatewayFactory.get_paper_importer(force_user=getattr(args, 'user', False))
            count = importer.fetch_missing_pdfs(args.collection, args.verbose)
            print(f"Fetched {count} PDFs.")
        elif args.action == "strip":
             from zotero_cli.infra.factory import GatewayFactory
             importer = GatewayFactory.get_paper_importer(force_user=getattr(args, 'user', False))
             count = importer.remove_attachments_from_folder(args.collection, args.verbose)
             print(f"Removed {count} attachments.")

    def _handle_duplicates(self, gateway, args):
        service = DuplicateFinder(gateway)
        col_ids = [c.strip() for c in args.collections.split(',')]
        dupes = service.find_duplicates(col_ids)
        if not dupes:
            print("No duplicates found.")
            return
        table = Table(title="Duplicate Items")
        table.add_column("Title")
        table.add_column("DOI")
        table.add_column("Keys")
        for d in dupes:
            table.add_row(d['title'], d['doi'] or 'N/A', ", ".join(d['keys']))
        console.print(table)

    def _handle_move(self, gateway, args):
        service = CollectionService(gateway)
        if service.move_item(args.item_id, args.source, args.target):
            print(f"Moved item {args.item_id} from {args.source} to {args.target}.")
        else:
            print("Failed to move item.")

    def _handle_clean(self, gateway, args):
        service = CollectionService(gateway)
        count = service.empty_collection(args.collection, args.parent, args.verbose)
        print(f"Deleted {count} items.")

    def _handle_migrate(self, gateway, args):
        service = MigrationService(gateway)
        results = service.migrate_collection_notes(args.collection, args.dry_run)
        print(f"Migration results for {args.collection}:")
        print(f"  Processed: {results['processed']}")
        print(f"  Migrated:  {results['migrated']}")
        print(f"  Failed:    {results['failed']}")

    def _handle_sync_csv(self, gateway, args):
        service = SyncService(gateway)
        
        def cli_progress(current, total, msg):
            percent = (current / total * 100) if total > 0 else 0
            sys.stdout.write(f"\r[{percent:5.1f}%] {msg:<60}")
            sys.stdout.flush()

        print(f"Syncing local CSV from '{args.collection}' notes...")
        success = service.recover_state_from_notes(args.collection, args.output, cli_progress)
        print("")
        if success:
            print(f"Successfully recovered state to '{args.output}'.")
        else:
            sys.exit(1)