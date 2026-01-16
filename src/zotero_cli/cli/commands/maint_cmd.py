import argparse
from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.duplicate_service import DuplicateFinder
from zotero_cli.core.services.migration_service import MigrationService
from zotero_cli.core.services.sync_service import SyncService
from rich.console import Console
from rich.table import Table

console = Console()

@CommandRegistry.register
class MaintCommand(BaseCommand):
    name = "maint"
    help = "Library Maintenance (dedupe, pdfs, sync)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)
        
        # Dedupe
        dedupe_p = sub.add_parser("dedupe", help="Find duplicates in collections")
        dedupe_p.add_argument("--collections", required=True, help="Comma-separated names or keys")

        # PDFs
        pdf_p = sub.add_parser("pdfs", help="Manage attachments")
        pdf_p.add_argument("action", choices=["fetch", "strip"])
        pdf_p.add_argument("--collection", required=True)
        pdf_p.add_argument("--verbose", action="store_true")

        # Migrate
        mig_p = sub.add_parser("migrate", help="Migrate audit notes to SDB v1.1")
        mig_p.add_argument("--collection", required=True)
        mig_p.add_argument("--dry-run", action="store_true")

        # Sync-CSV
        sync_p = sub.add_parser("sync-csv", help="Recover local CSV state from Zotero notes")
        sync_p.add_argument("--collection", required=True)
        sync_p.add_argument("--output", required=True)

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        
        if args.verb == "dedupe":
            self._handle_dedupe(gateway, args)
        elif args.verb == "pdfs":
            self._handle_pdfs(gateway, args)
        elif args.verb == "migrate":
            self._handle_migrate(gateway, args)
        elif args.verb == "sync-csv":
            self._handle_sync_csv(gateway, args)

    def _handle_dedupe(self, gateway, args):
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

    def _handle_pdfs(self, gateway, args):
        importer = GatewayFactory.get_paper_importer(force_user=getattr(args, 'user', False))
        if args.action == "fetch":
            count = importer.fetch_missing_pdfs(args.collection, args.verbose)
            print(f"Fetched {count} PDFs.")
        elif args.action == "strip":
             count = importer.remove_attachments_from_folder(args.collection, args.verbose)
             print(f"Removed {count} attachments.")

    def _handle_migrate(self, gateway, args):
        service = MigrationService(gateway)
        results = service.migrate_collection_notes(args.collection, args.dry_run)
        print(f"Migration results: {results}")

    def _handle_sync_csv(self, gateway, args):
        service = SyncService(gateway)
        print(f"Syncing local CSV from '{args.collection}'...")
        success = service.recover_state_from_notes(args.collection, args.output)
        if success: print(f"Recovered state to '{args.output}'.")
