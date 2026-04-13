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
        screen_p = sub.add_parser(
            "screen",
            help="[🟡 MODIFICATION] Interactive Screening Interface (TUI)",
            description="Initializes a text-based user interface for rapid item screening. Fetches pending items and records decisions automatically to SDB notes.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Rapid Abstract Screening
Problem: I have 200 papers in my "Unscreened" folder and I need to review their abstracts quickly.
Action:  zotero-cli slr screen --source "Unscreened" --include "Accepted" --exclude "Rejected"
Result:  The TUI launches, displaying the first abstract. Decisions will automatically move items into the Accepted or Rejected folders.

Cognitive Safeguards
--------------------
• Common Failure Modes: Forgetting to specify --include or --exclude. The decision is recorded, but the item isn't moved.
• Safety Tips: Always define your target collections to ensure your workflow is continuous and items are properly triaged.
"""
        )
        ScreenCommand.register_args(screen_p)
        # Compatibility for --file in screen (Issue #97 legacy)
        screen_p.add_argument("--file", help="Bulk process decisions from CSV")

        decide_p = sub.add_parser(
            "decide",
            help="[🟡 MODIFICATION] Record a single screening decision",
            description="Records a single screening decision (Include/Exclude) for an item, updating Screening Database (SDB) notes and optionally moving the item between collections. Ensures traceability of persona, phase, and rationale.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Manually excluding a paper during Abstract Review
Problem: I am reading an abstract and realized it's a survey paper, which violates my inclusion criteria.
Action:  zotero-cli slr decide --key "ABCD1234" --vote "EXCLUDE" --code "EXC02" --reason "Is a survey paper" --phase "title_abstract"
Result:  The item "ABCD1234" gets a new child note recording the exclusion by the human persona, timestamped and categorized under the title_abstract phase.

Cognitive Safeguards
--------------------
• Common Failure Modes: Forgetting the --code when excluding. The command will fail fast to prevent incomplete audit trails.
• Safety Tips: Use quick flags like --is-survey or --not-english to streamline frequent, repetitive exclusion reasons and avoid typos.
"""
        )
        DecideCommand.register_args(decide_p)

        load_p = sub.add_parser(
            "load",
            help="[🟡 MODIFICATION] Bulk-import screening decisions from CSV",
            description="Bulk-imports screening decisions from an external CSV file into your Zotero library. Performs a Matching Phase (Key/DOI) and updates metadata notes. Always run without --force first for a dry-run.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Importing Rayyan Decisions
Problem: I screened 500 papers in Rayyan and exported a CSV. I need these decisions reflected in Zotero for my final audit.
Action:  zotero-cli slr load --file "rayyan_export.csv" --reviewer "Chicout" --phase "full_text" --move-to-included "Accepted" --force
Result:  500 papers have their Zotero notes updated with "Chicout", "full_text", and "Accepted" status.

Cognitive Safeguards
--------------------
• Common Failure Modes: CSV column headers not matching the default expectations ('Key', 'Vote', 'Reason'). Use --col-* flags to override mappings.
• Safety Tips: Always perform a dry run (omit --force) and review the results table for "Matched Items" before applying.
"""
        )
        LoadCommand.register_args(load_p)

        # --- Verification ---
        verify_p = sub.add_parser(
            "verify",
            help="Unified verification (Collection or LaTeX)",
            description="Unified tool for verifying the metadata completeness of a collection or ensuring that all citations in a LaTeX manuscript exist within your Zotero library.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Pre-submission check of a LaTeX paper
Problem: I'm finishing my paper and want to make sure I haven't cited any papers that are missing from my Master Zotero Library.
Action:  zotero-cli slr verify --latex "main.tex"
Result:  The CLI lists citation keys found in the .tex file that do not have matching entries in Zotero.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to verify a LaTeX file using citation keys that don't match the Zotero extra field or CitationKey metadata.
• Safety Tips: Use --collection during the review phase to maintain metadata quality, and --latex during the writing phase to prevent technical errors.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_verify.md
""",
        )
        VerifyCommand.register_args(verify_p)

        # --- Snowballing ---
        snow_p = sub.add_parser(
            "snowball",
            help="Citation tracking (Snowballing) tools",
            description="Executes Forward and Backward Snowballing (citation tracking) to recursively discover new research papers based on a set of seed articles.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Expanding a review from a single seminal paper
Problem: I've found one "perfect" paper and I want to find everything it cites and everything that has cited it since.
Action:  zotero-cli slr snowball seed --doi "10.1145/1234.567" then zotero-cli slr snowball discovery.
Result:  The CLI builds a graph of related papers, which I can then review via slr snowball review.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting discovery on papers without DOIs. Snowballing relies on persistent identifiers for citation tracking.
• Safety Tips: Snowballing can quickly lead to "Context Explosion." Use the review TUI frequently to prune irrelevant branches.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_snowball.md
"""
        )
        SnowballCommand.register_args(snow_p)

        # --- SDB Maintenance ---
        sdb_p = sub.add_parser(
            "sdb",
            help="Screening DB (SDB) maintenance",
            description="Manages the internal Screening Database (SDB) notes associated with Zotero items, allowing for inspection, modification, or schema migration of the audit trail.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Verifying the audit history of a controversial paper
Problem: I want to see how many different reviewers screened paper ABCD1234 and what their final consensus was.
Action:  zotero-cli slr sdb inspect --key "ABCD1234"
Result:  The CLI displays a table showing every decision entry for that paper, timestamped and attributed to individual personas.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to edit a note that doesn't exist.
• Safety Tips: Use upgrade before running major reports (like report prisma) to ensure data consistency.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_sdb.md
"""
        )
        SDBCommand.register_args(sdb_p)

        # --- Extraction ---
        ext_p = sub.add_parser(
            "extract",
            help="Data Extraction tools",
            description="Systematically extracts research variables, methodologies, and quantitative results from the full text of research papers, optionally using AI agents.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Building a summary table of research methods
Problem: I have 30 included papers and I want to know the primary research method used in each without re-reading all of them.
Action:  zotero-cli slr extract --collection "INCLUDED_PAPERS" --agent --export "methods_matrix.json"
Result:  The CLI processes the papers and generates a JSON file summarizing the methodologies discovered by the AI agent.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting extraction on items that haven't been processed by rag ingest.
• Safety Tips: AI extraction is a heuristic process. Always manually verify a subset of the extracted data.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_extract.md
"""
        )
        ExtractionCommand.register_args(ext_p)

        # --- Analysis ---
        lookup_p = sub.add_parser(
            "lookup",
            help="Bulk metadata fetch",
            description="Quickly retrieves specific metadata fields for a batch of Zotero items using their unique keys, outputting the results in a formatted table or JSON.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Verifying DOIs for a set of citations
Problem: I have 10 item keys and I want to quickly see their DOIs to make sure they are all present.
Action:  zotero-cli slr lookup --keys "ABCD1234,WXYZ5678" --fields "DOI,title"
Result:  The CLI displays a clean table with the title and DOI for each of the specified keys.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to lookup keys that do not exist in the active library context.
• Safety Tips: Use --fields to limit the output to only what you need, reducing terminal clutter.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_lookup.md
"""
        )
        lookup_p.add_argument("--keys")
        lookup_p.add_argument("--file")
        lookup_p.add_argument("--fields", default="key,arxiv_id,title,date,url")
        lookup_p.add_argument("--format", default="table")

        graph_p = sub.add_parser(
            "graph",
            help="Citation Graph",
            description="Generates a visual citation graph (network map) representing the relationships between papers across one or more collections.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Visualizing the structure of a research field
Problem: I have two folders, "Transformers" and "CNNs," and I want to see how much these two fields cite each other.
Action:  zotero-cli slr graph --collections "TRANS_01,CNN_01"
Result:  The CLI outputs Mermaid code that, when rendered, shows a network of nodes (papers) and edges (citations).

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to graph very large collections (>200 items) which can lead to a "Spaghetti Graph."
• Safety Tips: Use this command on smaller, curated "Selection" folders to maintain visual clarity.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_graph.md
"""
        )
        graph_p.add_argument("--collections", required=True)

        shift_p = sub.add_parser(
            "shift",
            help="Detect items that moved between collections",
            description="Compares two Zotero library snapshots to identify research items that have moved between collections, facilitating the tracking of review progress over time.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Verifying papers moved during Title screening
Problem: I want to confirm that all papers I accepted yesterday have correctly moved from my "Unscreened" folder to "Accepted."
Action:  zotero-cli slr shift --old "yesterday.json" --new "today.json"
Result:  The CLI displays a list of papers that shifted their collection affiliation between the two snapshots.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to compare snapshots from different libraries or using malformed JSON files.
• Safety Tips: Use report snapshot regularly to maintain a versioned history of your library state.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_shift.md
"""
        )
        shift_p.add_argument("--old", required=True, help="Old Snapshot JSON")
        shift_p.add_argument("--new", required=True, help="New Snapshot JSON")

        # --- Utilities ---
        mig_p = sub.add_parser(
            "migrate",
            help="Migrate audit notes to newer schema versions",
            description="Upgrades the internal format of screening/audit notes for all items in a collection to match the latest standards of the zotero-cli.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Updating an old research project for a new report
Problem: I'm trying to run a PRISMA report on an SLR I started two years ago, but the command isn't recognizing my old decisions.
Action:  zotero-cli slr migrate --collection "OLD_SLR_FOLDER" --dry-run
Result:  The CLI shows that it can upgrade 100 legacy notes to the new format.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to migrate items that do not have any audit metadata at all.
• Safety Tips: Always perform a collection backup before running a migration on a critical collection.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_migrate.md
"""
        )
        mig_p.add_argument("--collection", required=True, help="Collection name or key")
        mig_p.add_argument("--dry-run", action="store_true", help="Show changes without applying")

        sync_p = sub.add_parser(
            "sync-csv",
            help="Recover/Sync local CSV from Zotero screening notes",
            description="Exports the current state of screening decisions from Zotero into a local CSV file, effectively creating an offline 'mirror' of your research audit trail.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Preparing data for statistical analysis
Problem: I've finished screening my papers in Zotero and I want to generate a spreadsheet showing the breakdown of exclusion reasons.
Action:  zotero-cli slr sync-csv --collection "SCREENING_PHASE_1" --output "screening_data.csv"
Result:  A CSV file is created that lists every paper and its corresponding decision metadata.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to sync to a file that is already open in another application (like Excel).
• Safety Tips: Use this command as a "Backup" mechanism for your screening results.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/slr_sync_csv.md
"""
        )
        sync_p.add_argument("--collection", required=True, help="Collection name or key")
        sync_p.add_argument("--output", required=True, help="Path to output CSV")

        prune_p = sub.add_parser(
            "prune",
            help="[🔴 DESTRUCTIVE] Enforce mutual exclusivity between two collections",
            description="Removes items from the '--excluded' collection if they already exist in the '--included' collection. Ensures datasets are disjoint for PRISMA reporting. Does not delete items from the library, only unlinks them from the excluded collection.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Cleaning the Excluded set after Full Text Review
Problem: During the screening, some papers were accidentally left in the "Excluded" folder after being promoted to the "Included" folder. This is skewing my PRISMA statistics.
Action:  zotero-cli slr prune --included "Full Text Included" --excluded "Full Text Excluded"
Result:  Any paper found in both folders is removed from "Full Text Excluded," leaving the folders perfectly disjoint.

Cognitive Safeguards
--------------------
• Common Failure Modes: Providing the wrong collection name. If the name is ambiguous (multiple collections with the same name), use the Zotero Collection Key instead.
• Safety Tips: Always run a `report status` or `report prisma` before and after pruning to verify the count changes as expected.
"""
        )
        prune_p.add_argument("--included", required=True, help="Primary collection (Winner/Included)")
        prune_p.add_argument(
            "--excluded",
            required=True,
            help="Secondary collection (Loser/Excluded - items removed from here)",
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
