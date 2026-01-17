import argparse
import sys

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.tui import TuiScreeningService
from zotero_cli.core.services.migration_service import MigrationService


class ScreenCommand(BaseCommand):
    name = "screen"
    help = "Interactive Screening Interface (TUI)"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--source", required=True, help="Source collection")
        parser.add_argument("--include", required=True, help="Target for inclusion")
        parser.add_argument("--exclude", required=True, help="Target for exclusion")
        parser.add_argument("--file", help="CSV file for bulk decisions (Headless mode)")
        parser.add_argument("--state", help="Local CSV file to track screening state")

    def execute(self, args: argparse.Namespace):
        if args.file:
            self._handle_bulk(args)
        else:
            self._handle_tui(args)

    def _handle_tui(self, args):
        from zotero_cli.core.services.screening_state import ScreeningStateService
        from zotero_cli.infra.factory import GatewayFactory

        state_manager = ScreeningStateService(args.state) if args.state else None

        service = GatewayFactory.get_screening_service(force_user=getattr(args, "user", False))
        tui = TuiScreeningService(service, state_manager)
        tui.run_screening_session(args.source, args.include, args.exclude)

    def _handle_bulk(self, args):
        from zotero_cli.infra.factory import GatewayFactory

        service = GatewayFactory.get_screening_service(force_user=getattr(args, "user", False))
        print(f"Processing bulk decisions from {args.file}...")

        import csv

        success_count = 0
        fail_count = 0

        try:
            with open(args.file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = row.get("Key")
                    vote = row.get("Vote")
                    reason = row.get("Reason", "")

                    if not key or not vote:
                        continue

                    if service.record_decision(
                        item_key=key,
                        decision=vote,
                        code="bulk",
                        reason=reason,
                        source_collection=args.source,
                        target_collection=args.include if vote == "INCLUDE" else args.exclude,
                    ):
                        success_count += 1
                    else:
                        fail_count += 1
            print(f"Done. Success: {success_count}, Failed: {fail_count}")
        except Exception as e:
            print(f"Error processing CSV: {e}")


class DecideCommand(BaseCommand):
    name = "decide"
    help = "Record a single decision (CLI mode)"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--key", required=True)
        parser.add_argument(
            "--vote",
            choices=["INCLUDE", "EXCLUDE"],
            help="Decision vote (required unless flag used)",
        )
        parser.add_argument(
            "--code", help="Exclusion/Inclusion criteria code (required unless flag used)"
        )
        parser.add_argument("--reason")
        parser.add_argument("--source")
        parser.add_argument("--target")
        parser.add_argument("--agent-led", action="store_true")
        parser.add_argument("--persona")
        parser.add_argument("--phase", default="title_abstract")

        # Exclusion presets
        parser.add_argument(
            "--short-paper", metavar="CODE", help="Exclude as Short Paper with EC code"
        )
        parser.add_argument(
            "--not-english", metavar="CODE", help="Exclude as Non-English with EC code"
        )
        parser.add_argument(
            "--is-survey", metavar="CODE", help="Exclude as Survey/SLR with EC code"
        )
        parser.add_argument(
            "--no-pdf", metavar="CODE", help="Exclude due to missing PDF with EC code"
        )

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory

        service = GatewayFactory.get_screening_service(force_user=getattr(args, "user", False))

        vote = args.vote
        code = args.code
        reason = args.reason

        # Resolve flags to decision
        if args.short_paper:
            vote, code, reason = "EXCLUDE", args.short_paper, "Short Paper"
        elif args.not_english:
            vote, code, reason = "EXCLUDE", args.not_english, "Not English"
        elif args.is_survey:
            vote, code, reason = "EXCLUDE", args.is_survey, "SLR/Survey"
        elif args.no_pdf:
            vote, code, reason = "EXCLUDE", args.no_pdf, "No PDF"

        if not vote or not code:
            from rich.console import Console

            console = Console()
            console.print(
                "[bold red]Error:[/bold red] You must provide --vote and --code OR use one of the exclusion flags (e.g., --short-paper EC5)."
            )
            sys.exit(1)

        agent_name = args.persona if args.agent_led else "human"

        success = service.record_decision(
            item_key=args.key,
            decision=vote,
            code=code,
            reason=reason,
            source_collection=args.source,
            target_collection=args.target,
            agent="zotero-cli",
            persona=agent_name,
            phase=args.phase,
        )

        if success:
            print(f"Successfully recorded decision for {args.key} ({vote}: {reason})")
        else:
            print(f"Failed to record decision for {args.key}")
            sys.exit(1)


@CommandRegistry.register
class ReviewCommand(BaseCommand):
    name = "review"
    help = "Systematic Review Workflow (Screening, Auditing, Syncing)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # Screen
        screen_p = sub.add_parser("screen", help=ScreenCommand.help)
        ScreenCommand().register_args(screen_p)

        # Decide
        decide_p = sub.add_parser("decide", help=DecideCommand.help)
        DecideCommand().register_args(decide_p)

        # Audit
        audit_p = sub.add_parser(
            "audit", help="Check collection for missing data (DOI, PDF, Notes)"
        )
        audit_p.add_argument("--collection", required=True, help="Collection name or key")
        audit_p.add_argument("--verbose", action="store_true", help="Show exact items missing data")

        # Migrate
        mig_p = sub.add_parser("migrate", help="Migrate audit notes to newer schema versions")
        mig_p.add_argument("--collection", required=True, help="Collection name or key")
        mig_p.add_argument("--dry-run", action="store_true", help="Show changes without applying")

        # Sync-CSV
        sync_p = sub.add_parser(
            "sync-csv", help="Recover/Sync local CSV from Zotero screening notes"
        )
        sync_p.add_argument("--collection", required=True, help="Collection name or key")
        sync_p.add_argument("--output", required=True, help="Path to output CSV")

        # Prune
        prune_p = sub.add_parser("prune", help="Enforce mutual exclusivity between two collections")
        prune_p.add_argument("--included", required=True, help="Primary collection (Winner)")
        prune_p.add_argument(
            "--excluded",
            required=True,
            help="Secondary collection (Loser - items removed from here)",
        )

    def execute(self, args: argparse.Namespace):
        if args.verb == "screen":
            ScreenCommand().execute(args)
        elif args.verb == "decide":
            DecideCommand().execute(args)
        elif args.verb == "audit":
            self._handle_audit(args)
        elif args.verb == "migrate":
            self._handle_migrate(args)
        elif args.verb == "sync-csv":
            self._handle_sync_csv(args)
        elif args.verb == "prune":
            self._handle_prune(args)

    def _handle_prune(self, args):
        from zotero_cli.infra.factory import GatewayFactory

        service = GatewayFactory.get_collection_service(force_user=getattr(args, "user", False))

        print(f"Pruning intersection: '{args.included}' vs '{args.excluded}'...")
        count = service.prune_intersection(args.included, args.excluded)

        if count > 0:
            print(f"[bold green]Pruned {count} items from '{args.excluded}'.")
        else:
            print("No intersection found. Sets are disjoint.")

    def _handle_audit(self, args):
        from rich.console import Console
        from rich.table import Table

        from zotero_cli.core.services.audit_service import CollectionAuditor
        from zotero_cli.infra.factory import GatewayFactory

        console = Console()

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))
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

        has_failures = any(
            [
                report.items_missing_id,
                report.items_missing_pdf,
                report.items_missing_note,
                report.items_missing_title,
                report.items_missing_abstract,
            ]
        )

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

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))
        service = MigrationService(gateway)
        results = service.migrate_collection_notes(args.collection, args.dry_run)
        print(f"Migration results for {args.collection}:")
        print(f"  Processed: {results['processed']}")
        print(f"  Migrated:  {results['migrated']}")
        print(f"  Failed:    {results['failed']}")

    def _handle_sync_csv(self, args):
        from zotero_cli.core.services.sync_service import SyncService
        from zotero_cli.infra.factory import GatewayFactory

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))
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
