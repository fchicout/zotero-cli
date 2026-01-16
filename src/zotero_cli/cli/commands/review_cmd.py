import argparse
import sys

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.migration_service import MigrationService


@CommandRegistry.register
class ReviewCommand(BaseCommand):
    name = "review"
    help = "Systematic Review Workflow (Screening, Auditing, Syncing)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        from zotero_cli.cli.commands.screen_cmd import DecideCommand, ScreenCommand

        # Screen
        screen_p = sub.add_parser("screen", help=ScreenCommand.help)
        ScreenCommand().register_args(screen_p)

        # Decide
        decide_p = sub.add_parser("decide", help=DecideCommand.help)
        DecideCommand().register_args(decide_p)

        # Audit
        audit_p = sub.add_parser("audit", help="Check collection for missing data (DOI, PDF, Notes)")
        audit_p.add_argument("--collection", required=True, help="Collection name or key")
        audit_p.add_argument("--verbose", action="store_true", help="Show exact items missing data")

        # Migrate
        mig_p = sub.add_parser("migrate", help="Migrate audit notes to newer schema versions")
        mig_p.add_argument("--collection", required=True, help="Collection name or key")
        mig_p.add_argument("--dry-run", action="store_true", help="Show changes without applying")

        # Sync-CSV
        sync_p = sub.add_parser("sync-csv", help="Recover/Sync local CSV from Zotero screening notes")
        sync_p.add_argument("--collection", required=True, help="Collection name or key")
        sync_p.add_argument("--output", required=True, help="Path to output CSV")

    def execute(self, args: argparse.Namespace):
        if args.verb == "screen":
            from zotero_cli.cli.commands.screen_cmd import ScreenCommand
            ScreenCommand().execute(args)
        elif args.verb == "decide":
            from zotero_cli.cli.commands.screen_cmd import DecideCommand
            DecideCommand().execute(args)
        elif args.verb == "audit":
            self._handle_audit(args)
        elif args.verb == "migrate":
            self._handle_migrate(args)
        elif args.verb == "sync-csv":
            self._handle_sync_csv(args)

    def _handle_audit(self, args):
        from rich.console import Console
        from rich.table import Table

        from zotero_cli.core.services.audit_service import CollectionAuditor
        from zotero_cli.infra.factory import GatewayFactory
        console = Console()

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        service = CollectionAuditor(gateway)
        print(f"Auditing collection: {args.collection}...")
        report = service.audit_collection(args.collection)

        if not report:
            sys.exit(1)

        table = Table(title=f"Audit Report: {args.collection}")
        table.add_column("Rule", style="cyan")
        table.add_column("Status", justify="right")
        table.add_column("Missing", justify="right", style="red")

        def add_row(name, items):
            status = "[green]PASS[/green]" if not items else "[red]FAIL[/red]"
            table.add_row(name, status, str(len(items)))

        add_row("DOI / arXiv ID", report.items_missing_id)
        add_row("Title", report.items_missing_title)
        add_row("Abstract", report.items_missing_abstract)
        add_row("PDF Attachment", report.items_missing_pdf)
        add_row("Screening Note", report.items_missing_note)

        console.print(table)
        print(f"Total items analyzed: {report.total_items}")

        has_failures = any([
            report.items_missing_id, report.items_missing_pdf,
            report.items_missing_note, report.items_missing_title,
            report.items_missing_abstract
        ])

        if args.verbose and has_failures:
            print("\n--- Failure Details ---")
            if report.items_missing_id:
                print(f"Missing ID: {', '.join([i.key for i in report.items_missing_id])}")
            if report.items_missing_pdf:
                print(f"Missing PDF: {', '.join([i.key for i in report.items_missing_pdf])}")
            if report.items_missing_note:
                print(f"Missing Note: {', '.join([i.key for i in report.items_missing_note])}")

        if has_failures:
            print("\n[bold red]Audit FAILED.[/bold red] Some items are not submission-ready.")
            sys.exit(1)
        else:
            print("\n[bold green]Audit PASSED.[/bold green] All items are submission-ready.")

    def _handle_migrate(self, args):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        service = MigrationService(gateway)
        results = service.migrate_collection_notes(args.collection, args.dry_run)
        print(f"Migration results for {args.collection}:")
        print(f"  Processed: {results['processed']}")
        print(f"  Migrated:  {results['migrated']}")
        print(f"  Failed:    {results['failed']}")

    def _handle_sync_csv(self, args):
        from zotero_cli.core.services.sync_service import SyncService
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
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
