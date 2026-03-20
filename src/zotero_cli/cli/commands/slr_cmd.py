import argparse
import json
import sys

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.commands.slr import (
    DecideCommand,
    ExtractionCommand,
    LoadCommand,
    SDBCommand,
    ScreenCommand,
    SnowballCommand,
    VerifyCommand,
)
from zotero_cli.core.services.audit_service import CollectionAuditor
from zotero_cli.core.services.graph_service import CitationGraphService
from zotero_cli.core.services.lookup_service import LookupService
from zotero_cli.core.services.migration_service import MigrationService
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class SLRCommand(BaseCommand):
    name = "slr"
    help = "Systematic Literature Review (SLR) tools"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # --- Screening ---
        screen_p = sub.add_parser("screen", help="Interactive Screening Interface (TUI)")
        ScreenCommand.register_args(screen_p)
        # Compatibility for --file in screen (Issue #97 legacy)
        screen_p.add_argument("--file", help="Bulk process decisions from CSV")

        decide_p = sub.add_parser("decide", help="Record a single screening decision")
        DecideCommand.register_args(decide_p)

        load_p = sub.add_parser("load", help="Import screening decisions from CSV")
        LoadCommand.register_args(load_p)

        # --- Verification ---
        verify_p = sub.add_parser("verify", help="Unified verification (Collection or LaTeX)")
        VerifyCommand.register_args(verify_p)

        # --- Snowballing ---
        snow_p = sub.add_parser("snowball", help="Citation tracking (Snowballing) tools")
        SnowballCommand.register_args(snow_p)

        # --- SDB Maintenance ---
        sdb_p = sub.add_parser("sdb", help="Screening DB (SDB) maintenance")
        SDBCommand.register_args(sdb_p)

        # --- Extraction ---
        ext_p = sub.add_parser("extract", help="Data Extraction tools")
        ExtractionCommand.register_args(ext_p)

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

        # --- Reset ---
        reset_p = sub.add_parser("reset", help="Reset screening/audit metadata for a collection")
        reset_p.add_argument("--name", required=True, help="Collection name or key")
        reset_p.add_argument("--phase", required=True, help="Target phase to reset")
        reset_p.add_argument("--persona", help="Reviewer persona to reset (Optional)")
        reset_p.add_argument("--force", action="store_true", help="Skip confirmation")

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "screen":
            if getattr(args, "file", None):
                self._handle_bulk_decide(args)
            else:
                ScreenCommand.execute(args)
        elif args.verb == "decide":
            DecideCommand.execute(args)
        elif args.verb == "load":
            LoadCommand.execute(gateway, args)
        elif args.verb == "verify":
            VerifyCommand.execute(gateway, args)
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
            ExtractionCommand.execute(args)
        elif args.verb == "sdb":
            SDBCommand.execute(gateway, args)
        elif args.verb == "reset":
            self._handle_reset(gateway, args)
        elif args.verb == "snowball":
            SnowballCommand.execute(gateway, args)

    # Temporary handlers until full decomposition
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
                        source_collection=args.source if hasattr(args, "source") else None,
                        target_collection=(
                            args.include if vote == "INCLUDE" else args.exclude
                        ) if hasattr(args, "include") else None,
                    ):
                        success_count += 1
                    else:
                        fail_count += 1
            print(f"Done. Success: {success_count}, Failed: {fail_count}")
        except Exception as e:
            print(f"Error processing CSV: {e}")

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

    def _handle_reset(self, gateway, args):
        from rich.prompt import Confirm

        from zotero_cli.core.services.purge_service import PurgeService

        # 1. Resolve Items
        col_id = gateway.get_collection_id_by_name(args.name)
        if not col_id:
            col_id = args.name
        items = list(gateway.get_items_in_collection(col_id))
        if not items:
            console.print(f"[yellow]No items found in '{args.name}'.[/yellow]")
            return

        keys = [i.key for i in items]

        # 2. Confirmation
        if not args.force:
            if not Confirm.ask(
                f"Are you sure you want to reset {args.phase} metadata for {len(keys)} items in '{args.name}'?"
            ):
                return

        # 3. Purge
        service = PurgeService(gateway)
        dry_run = not args.force

        note_stats = service.purge_notes(
            keys, sdb_only=True, phase=args.phase, persona=args.persona, dry_run=dry_run
        )
        tag_name = f"rsl:phase:{args.phase}"
        tag_stats = service.purge_tags(keys, tag_name=tag_name, dry_run=dry_run)

        console.print(f"\n[bold]Reset results for '{args.name}' (Phase: {args.phase}):[/bold]")
        console.print(f" - Notes purged: {note_stats['deleted']}")
        console.print(f" - Tags purged:  {tag_stats['deleted']}")
        if dry_run:
            console.print("[yellow]DRY RUN COMPLETE. No changes applied.[/yellow]")
        else:
            console.print("[bold green]Reset complete.[/bold green]")
