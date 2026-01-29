import argparse
import json
import sys

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.tui.extraction_tui import ExtractionTUI
from zotero_cli.cli.tui.screening_tui import TuiScreeningService
from zotero_cli.core.services.audit_service import CollectionAuditor
from zotero_cli.core.services.extraction_service import (
    ExtractionSchemaValidator,
    ExtractionService,
)
from zotero_cli.core.services.graph_service import CitationGraphService
from zotero_cli.core.services.lookup_service import LookupService
from zotero_cli.core.services.migration_service import MigrationService
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.infra.opener import OpenerService

console = Console()


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
        decide_p.add_argument("--reason", help="Detailed reason text")
        decide_p.add_argument("--evidence", help="Evidence extracted from text (SDB v1.2)")
        decide_p.add_argument("--source")
        decide_p.add_argument("--target")
        decide_p.add_argument("--agent-led", action="store_true")
        decide_p.add_argument("--persona")
        decide_p.add_argument(
            "--phase",
            choices=["title_abstract", "full_text"],
            default="title_abstract",
            help="Screening phase (Isolation enabled)",
        )

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

        # --- Data Loading (formerly audit import-csv) ---
        load_p = sub.add_parser("load", help="Retroactive SDB enrichment from CSV")
        load_p.add_argument("file", help="CSV file with screening decisions")
        load_p.add_argument("--reviewer", required=True, help="Reviewer name (persona)")
        load_p.add_argument(
            "--phase",
            choices=["title_abstract", "full_text"],
            default="title_abstract",
            help="Target phase for imported decisions",
        )
        load_p.add_argument(
            "--force", action="store_true", help="Actually write to Zotero (Default is Dry-Run)"
        )
        # Column mapping (Issue #62)
        load_p.add_argument("--col-key", help="CSV column for Zotero Key (Default: Key)")
        load_p.add_argument("--col-vote", help="CSV column for Decision/Vote (Default: Vote)")
        load_p.add_argument("--col-reason", help="CSV column for Reason Text (Default: Reason)")
        load_p.add_argument("--col-code", help="CSV column for Criteria Code (Default: Code)")
        load_p.add_argument("--col-doi", help="CSV column for DOI (Default: DOI)")
        load_p.add_argument("--col-title", help="CSV column for Title (Default: Title)")
        load_p.add_argument("--col-evidence", help="CSV column for Evidence (Default: Evidence)")

        # --- Validation (formerly audit check) ---
        val_p = sub.add_parser("validate", help="Check collection for metadata completeness")
        val_p.add_argument("--collection", required=True, help="Collection name or key")
        val_p.add_argument("--verbose", action="store_true", help="Show exact items missing data")

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

        # --- Extraction (Issue #42) ---
        ext_p = sub.add_parser("extract", help="Data Extraction management")
        ext_p.add_argument("--init", action="store_true", help="Initialize schema.yaml from template")
        ext_p.add_argument("--validate", action="store_true", help="Validate current schema.yaml")
        ext_p.add_argument(
            "--export",
            choices=["csv", "markdown", "json"],
            nargs="?",
            const="csv",
            help="Export synthesis matrix (Default: csv)",
        )
        ext_p.add_argument("target", nargs="?", help="Collection Name OR Item Key to extract from")
        ext_p.add_argument("--agent", default="zotero-cli", help="Agent name")
        ext_p.add_argument("--persona", default="unknown", help="Reviewer persona")

        # --- SDB Management (Issue #60) ---
        sdb_p = sub.add_parser("sdb", help="Screening Database (SDB) maintenance")
        sdb_sub = sdb_p.add_subparsers(dest="sdb_verb", required=True)

        # sdb inspect
        sdb_insp = sdb_sub.add_parser("inspect", help="Inspect SDB entries for an item")
        sdb_insp.add_argument("key", help="Item Key")

        # sdb edit
        sdb_edit = sdb_sub.add_parser("edit", help="Surgically edit an SDB entry")
        sdb_edit.add_argument("key", help="Item Key")
        sdb_edit.add_argument("--persona", required=True, help="Target Persona")
        sdb_edit.add_argument("--phase", required=True, help="Target Phase")
        sdb_edit.add_argument("--set-decision", choices=["accepted", "rejected"], help="Update decision")
        sdb_edit.add_argument("--set-criteria", help="Update criteria codes (comma-separated)")
        sdb_edit.add_argument("--set-reason", help="Update reason text")
        sdb_edit.add_argument("--set-reviewer", help="Update reviewer/persona name")
        sdb_edit.add_argument("--execute", action="store_true", help="Apply changes (Default: Dry-Run)")

        # sdb upgrade
        sdb_upg = sdb_sub.add_parser("upgrade", help="Upgrade SDB notes to latest schema (v1.2)")
        sdb_upg.add_argument("--collection", required=True, help="Target collection")
        sdb_upg.add_argument("--execute", action="store_true", help="Apply changes (Default: Dry-Run)")

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "screen":
            self._handle_screen(args)
        elif args.verb == "decide":
            self._handle_decide(args)
        elif args.verb == "load":
            self._handle_load(gateway, args)
        elif args.verb == "validate":
            self._handle_validate(gateway, args)
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
        elif args.verb == "extract":
            self._handle_extract(args)
        elif args.verb == "sdb":
            self._handle_sdb(gateway, args)

    def _handle_sdb(self, gateway, args):
        from zotero_cli.core.services.sdb.sdb_service import SDBService
        service = SDBService(gateway)

        if args.sdb_verb == "inspect":
            entries = service.inspect_item_sdb(args.key)
            if not entries:
                console.print(f"[yellow]No SDB entries found for item {args.key}[/yellow]")
                return
            table = service.build_inspect_table(args.key, entries)
            console.print(table)

        elif args.sdb_verb == "edit":
            dry_run = not args.execute
            updates = {}
            if args.set_decision:
                updates["decision"] = args.set_decision
            if args.set_criteria:
                updates["reason_code"] = [c.strip() for c in args.set_criteria.split(",")]
            if args.set_reason:
                updates["reason_text"] = args.set_reason
            if args.set_reviewer:
                updates["persona"] = args.set_reviewer
            
            if not updates:
                console.print("[red]Error: No updates specified. Use --set-* flags.[/red]")
                return

            success, msg = service.edit_sdb_entry(
                args.key, args.persona, args.phase, updates, dry_run=dry_run
            )
            style = "green" if success else "red"
            console.print(f"[{style}]{msg}[/{style}]")

        elif args.sdb_verb == "upgrade":
            dry_run = not args.execute
            if dry_run:
                console.print("[yellow]Running SDB Upgrade in DRY-RUN mode. Use --execute to apply.[/yellow]")
            
            stats = service.upgrade_sdb_entries(args.collection, dry_run=dry_run)
            console.print(f"Scanned: {stats['scanned']}, Upgraded: {stats['upgraded']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}")

    # --- Handlers ---

    def _handle_validate(self, gateway, args: argparse.Namespace):
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

    def _handle_load(self, gateway, args: argparse.Namespace):
        service = CollectionAuditor(gateway)
        dry_run = not args.force

        print(f"Importing SDB data from {args.file} (Reviewer: {args.reviewer})...")
        if dry_run:
            print("[bold yellow]DRY RUN MODE ENABLED. No changes will be written.[/bold yellow]")

        # Construct column map
        column_map = {}
        for internal, attr in [
            ("key", "col_key"),
            ("vote", "col_vote"),
            ("reason", "col_reason"),
            ("code", "col_code"),
            ("doi", "col_doi"),
            ("title", "col_title"),
            ("evidence", "col_evidence"),
        ]:
            val = getattr(args, attr, None)
            if val:
                column_map[internal] = val

        results = service.enrich_from_csv(
            csv_path=args.file,
            reviewer=args.reviewer,
            dry_run=dry_run,
            force=args.force,
            phase=args.phase,
            column_map=column_map,
        )

        if "error" in results:
            console.print(f"[bold red]Error:[/bold red] {results['error']}")
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
        if args.no_pdf:
            vote, code, reason = "EXCLUDE", args.no_pdf, "No PDF"

        if not vote:
            console.print("[bold red]Error:[/bold red] You must provide --vote.")
            sys.exit(1)

        if vote == "EXCLUDE" and not code:
            console.print(
                "[bold red]Error:[/bold red] You must provide --code for EXCLUDE decisions."
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
            evidence=args.evidence,
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

    def _handle_extract(self, args):
        # 1. Schema Management
        validator = ExtractionSchemaValidator()

        if args.init:
            try:
                if validator.init_schema():
                    console.print("[bold green]Created schema.yaml from template.[/bold green]")
                else:
                    console.print("[bold yellow]schema.yaml already exists. Skipping init.[/bold yellow]")
            except Exception as e:
                console.print(f"[bold red]Error initializing schema:[/bold red] {e}")
                sys.exit(1)
            return

        if args.validate:
            errors = validator.validate()
            if errors:
                console.print("[bold red]Schema Validation Failed:[/bold red]")
                for err in errors:
                    console.print(f" - {err}")
                sys.exit(1)
            else:
                console.print("[bold green]Schema is valid![/bold green]")
            return

        # 2. Extraction Session or Export
        if not args.target:
            console.print("[yellow]Please specify a Target (Collection or Item Key) to start extraction or export.[/yellow]")
            return

        # Initialize Service Stack
        force_user = getattr(args, "user", False)
        note_repo = GatewayFactory.get_note_repository(force_user=force_user)
        ext_service = ExtractionService(note_repo)

        # Resolve Target
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        # Try as Item Key first
        item = gateway.get_item(args.target)
        if item:
            items = [item]
        else:
            # Try as Collection
            col_id = gateway.get_collection_id_by_name(args.target)
            if col_id:
                items = list(gateway.get_items_in_collection(col_id))
            else:
                console.print(f"[bold red]Error:[/bold red] Could not find item or collection '{args.target}'")
                sys.exit(1)

        if args.export:
            console.print(f"Exporting synthesis matrix ({args.export}) for target '{args.target}'...")
            path = ext_service.export_matrix(items, output_format=args.export, persona=args.persona)
            console.print(f"[bold green]Matrix exported to: {path}[/bold green]")
            return

        # 3. Launch TUI
        opener = OpenerService()
        tui = ExtractionTUI(ext_service, opener)
        tui.run_extraction(items, agent=args.agent, persona=args.persona)
