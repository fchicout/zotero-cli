import argparse
import json
import sys

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.tui import TuiScreeningService
from zotero_cli.core.services.audit_service import CollectionAuditor
from zotero_cli.core.services.graph_service import CitationGraphService
from zotero_cli.core.services.lookup_service import LookupService
from zotero_cli.core.services.migration_service import MigrationService
from zotero_cli.infra.factory import GatewayFactory

console = Console()


class SLRAuditCommand:
    """Helper for slr audit subcommands."""

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="audit_verb", required=True)

        # Check
        check_p = sub.add_parser("check", help="Check collection for missing data")
        check_p.add_argument("--collection", required=True, help="Collection name or key")
        check_p.add_argument("--verbose", action="store_true", help="Show exact items missing data")

        # Import CSV
        import_csv_p = sub.add_parser("import-csv", help="Retroactive SDB enrichment from CSV")
        import_csv_p.add_argument("file", help="CSV file with screening decisions")
        import_csv_p.add_argument("--reviewer", required=True, help="Reviewer name (persona)")
        import_csv_p.add_argument(
            "--force", action="store_true", help="Actually write to Zotero (Default is Dry-Run)"
        )

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        service = CollectionAuditor(gateway)

        if args.audit_verb == "check":
            self._handle_check(service, args)
        elif args.audit_verb == "import-csv":
            self._handle_import_csv(service, args)

    def _handle_check(self, service: CollectionAuditor, args: argparse.Namespace):
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

    def _handle_import_csv(self, service: CollectionAuditor, args: argparse.Namespace):
        dry_run = not args.force

        print(f"Importing SDB data from {args.file} (Reviewer: {args.reviewer})...")
        if dry_run:
            print("[bold yellow]DRY RUN MODE ENABLED. No changes will be written.[/bold yellow]")

        results = service.enrich_from_csv(
            csv_path=args.file, reviewer=args.reviewer, dry_run=dry_run, force=args.force
        )

        if "error" in results:
            console.print(f"[bold red]Error:[/] {results['error']}")
            return

        table = Table(title="Import CSV Results")
        table.add_column("Metric")
        table.add_column("Value", justify="right")

        table.add_row("Total Rows", str(results["total_rows"]))
        table.add_row("Matched Items", f"[green]{results['matched']}[/]")
        table.add_row("Unmatched Rows", f"[red]{len(results['unmatched'])}[/]")
        table.add_row("Notes Updated", str(results["updated"]))
        table.add_row("Notes Created", str(results["created"]))
        table.add_row("Skipped (Dry Run)", str(results["skipped"]))

        console.print(table)

        if results["unmatched"]:
            print("\n[bold red]Unmatched Titles:[/]")
            for t in results["unmatched"][:10]:
                print(f"  - {t}")
            if len(results["unmatched"]) > 10:
                print(f"  ... and {len(results['unmatched']) - 10} more.")


@CommandRegistry.register
class SLRCommand(BaseCommand):
    name = "slr"
    help = "Systematic Literature Review lifecycle management"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # --- Screening ---
        screen_p = sub.add_parser("screen", help="Interactive Screening Interface (TUI)")
        screen_p.add_argument("--source", required=True, help="Source collection")
        screen_p.add_argument("--include", required=True, help="Target for inclusion")
        screen_p.add_argument("--exclude", required=True, help="Target for exclusion")
        screen_p.add_argument("--file", help="CSV file for bulk decisions (Headless mode)")
        screen_p.add_argument("--state", help="Local CSV file to track screening state")

        decide_p = sub.add_parser("decide", help="Record a single decision (CLI mode)")
        decide_p.add_argument("--key", required=True)
        decide_p.add_argument(
            "--vote",
            choices=["INCLUDE", "EXCLUDE"],
            help="Decision vote (required unless flag used)",
        )
        decide_p.add_argument(
            "--code", help="Exclusion/Inclusion criteria code (required unless flag used)"
        )
        decide_p.add_argument("--reason")
        decide_p.add_argument("--source")
        decide_p.add_argument("--target")
        decide_p.add_argument("--agent-led", action="store_true")
        decide_p.add_argument("--persona")
        decide_p.add_argument("--phase", default="title_abstract")

        # Decide Exclusion presets
        decide_p.add_argument(
            "--short-paper", metavar="CODE", help="Exclude as Short Paper with EC code"
        )
        decide_p.add_argument(
            "--not-english", metavar="CODE", help="Exclude as Non-English with EC code"
        )
        decide_p.add_argument(
            "--is-survey", metavar="CODE", help="Exclude as Survey/SLR with EC code"
        )
        decide_p.add_argument(
            "--no-pdf", metavar="CODE", help="Exclude due to missing PDF with EC code"
        )

        # --- Auditing ---
        audit_p = sub.add_parser("audit", help="Audit & SDB Enrichment")
        SLRAuditCommand().register_args(audit_p)

        # --- Analysis ---
        lookup_p = sub.add_parser("lookup", help="Bulk metadata fetch")
        lookup_p.add_argument("--keys")
        lookup_p.add_argument("--file")
        lookup_p.add_argument("--fields", default="key,arxiv_id,title,date,url")
        lookup_p.add_argument("--format", default="table")

        graph_p = sub.add_parser("graph", help="Citation Graph")
        graph_p.add_argument("--collections", required=True)

        shift_p = sub.add_parser("shift", help="Detect items that moved between collections")
        shift_p.add_argument("--old", required=True, help="Old Snapshot JSON")
        shift_p.add_argument("--new", required=True, help="New Snapshot JSON")

        # --- Utilities ---
        mig_p = sub.add_parser("migrate", help="Migrate audit notes to newer schema versions")
        mig_p.add_argument("--collection", required=True, help="Collection name or key")
        mig_p.add_argument("--dry-run", action="store_true", help="Show changes without applying")

        sync_p = sub.add_parser(
            "sync-csv", help="Recover/Sync local CSV from Zotero screening notes"
        )
        sync_p.add_argument("--collection", required=True, help="Collection name or key")
        sync_p.add_argument("--output", required=True, help="Path to output CSV")

        prune_p = sub.add_parser("prune", help="Enforce mutual exclusivity between two collections")
        prune_p.add_argument("--included", required=True, help="Primary collection (Winner)")
        prune_p.add_argument(
            "--excluded",
            required=True,
            help="Secondary collection (Loser - items removed from here)",
        )

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "screen":
            self._handle_screen(args)
        elif args.verb == "decide":
            self._handle_decide(args)
        elif args.verb == "audit":
            SLRAuditCommand().execute(args)
        elif args.verb == "lookup":
            self._handle_lookup(gateway, args)
        elif args.verb == "graph":
            self._handle_graph(gateway, args)
        elif args.verb == "shift":
            self._handle_shift(gateway, args)
        elif args.verb == "migrate":
            self._handle_migrate(gateway, args)
        elif args.verb == "sync-csv":
            self._handle_sync_csv(gateway, args)
        elif args.verb == "prune":
            self._handle_prune(args)

    # --- Handlers (Migrated) ---

    def _handle_screen(self, args):
        if args.file:
            self._handle_bulk_decide(args)
        else:
            from zotero_cli.core.services.screening_state import ScreeningStateService

            state_manager = ScreeningStateService(args.state) if args.state else None
            service = GatewayFactory.get_screening_service(force_user=getattr(args, "user", False))
            tui = TuiScreeningService(service, state_manager)
            tui.run_screening_session(args.source, args.include, args.exclude)

    def _handle_bulk_decide(self, args):
        import csv

        service = GatewayFactory.get_screening_service(force_user=getattr(args, "user", False))
        print(f"Processing bulk decisions from {args.file}...")
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

    def _handle_decide(self, args):
        service = GatewayFactory.get_screening_service(force_user=getattr(args, "user", False))
        vote = args.vote
        code = args.code
        reason = args.reason

        if args.short_paper:
            vote, code, reason = "EXCLUDE", args.short_paper, "Short Paper"
        elif args.not_english:
            vote, code, reason = "EXCLUDE", args.not_english, "Not English"
        elif args.is_survey:
            vote, code, reason = "EXCLUDE", args.is_survey, "SLR/Survey"
        elif args.no_pdf:
            vote, code, reason = "EXCLUDE", args.no_pdf, "No PDF"

        if not vote or not code:
            console.print(
                "[bold red]Error:[/bold red] You must provide --vote and --code OR use one of the exclusion flags."
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

    def _handle_lookup(self, gateway, args):
        service = LookupService(gateway)
        keys = args.keys.split(",") if args.keys else []
        if args.file:
            with open(args.file) as f:
                keys.extend([line.strip() for line in f if line.strip()])
        fields = args.fields.split(",")
        result = service.lookup_items(keys, fields, args.format)
        print(result)

    def _handle_graph(self, gateway, args):
        meta_service = GatewayFactory.get_metadata_aggregator()
        service = CitationGraphService(gateway, meta_service)
        col_ids = [c.strip() for c in args.collections.split(",")]
        dot = service.build_graph(col_ids)
        print(dot)

    def _handle_shift(self, gateway, args):
        service = CollectionAuditor(gateway)
        with open(args.old, "r") as f:
            old_data = json.load(f)
            snap_old = old_data.get("items", old_data) if isinstance(old_data, dict) else old_data
        with open(args.new, "r") as f:
            new_data = json.load(f)
            snap_new = new_data.get("items", new_data) if isinstance(new_data, dict) else new_data
        shifts = service.detect_shifts(snap_old, snap_new)
        if not shifts:
            console.print("[bold green]No shifts detected. State is stable.[/bold green]")
            return
        table = Table(title="Collection Shifts (Drift Detection)")
        table.add_column("Key")
        table.add_column("Title")
        table.add_column("From", style="red")
        table.add_column("To", style="green")
        for s in shifts:
            table.add_row(s["key"], s["title"][:50], ", ".join(s["from"]), ", ".join(s["to"]))
        console.print(table)

    def _handle_migrate(self, gateway, args):
        service = MigrationService(gateway)
        results = service.migrate_collection_notes(args.collection, args.dry_run)
        print(f"Migration results for {args.collection}:")
        print(f"  Processed: {results['processed']}")
        print(f"  Migrated:  {results['migrated']}")
        print(f"  Failed:    {results['failed']}")

    def _handle_sync_csv(self, gateway, args):
        from zotero_cli.core.services.sync_service import SyncService

        service = SyncService(gateway)

        def cli_progress(current, total, msg):
            percent = (current / total * 100) if total > 0 else 0
            sys.stdout.write(f"\r[{percent:5.1f}%] {msg:<60}")
            sys.stdout.flush()

        print(f"Syncing local CSV from '{args.collection}' notes...")
        success = service.recover_state_from_notes(args.collection, args.output, cli_progress)
        print("")
        if not success:
            sys.exit(1)

    def _handle_prune(self, args):
        service = GatewayFactory.get_collection_service(force_user=getattr(args, "user", False))
        print(f"Pruning intersection: '{args.included}' vs '{args.excluded}'...")
        count = service.prune_intersection(args.included, args.excluded)
        if count > 0:
            print(f"[bold green]Pruned {count} items from '{args.excluded}'.")
        else:
            print("No intersection found. Sets are disjoint.")
