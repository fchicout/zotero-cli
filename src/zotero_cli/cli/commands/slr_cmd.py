import argparse

from rich.console import Console

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.commands.slr import (
    DecideCommand,
    ExtractionCommand,
    ListCommand,
    LoadCommand,
    PromoteCommand,
    ReconcileCommand,
    ScreenCommand,
    SDBCommand,
    SnowballCommand,
)
from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand
from zotero_cli.cli.commands.slr.source_cmd import SLRSourceCommand
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class SLRCommand(BaseCommand):
    name = "slr"
    help = "Systematic Literature Review (SLR) workflow tools"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # --- Sub-Namespaces ---

        # slr report
        report_p = sub.add_parser(
            "report",
            help="SLR reporting and funnel analytics",
            description="Access subcommands for generating SLR status summaries, PRISMA diagrams, citation graphs, screening statistics, consensus discrepancy audits, and library collection drift reports.",
        )
        SLRReportCommand.register_args(report_p)

        # slr source
        source_p = sub.add_parser(
            "source",
            help="SLR Search Source Ingestion & Infrastructure",
            description="Allows for organizing, importing, and listing paper search sources in standard raw_ collections.",
        )
        SLRSourceCommand.register_args(source_p)

        # --- Screening ---
        screen_p = sub.add_parser(
            "screen",
            help="Interactive Screening Interface (TUI)",
            description="Initializes a text-based user interface for rapid item screening. Fetches pending items and records decisions automatically to SDB notes.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Rapid Abstract Screening
Problem: I have 200 papers in my "Unscreened" folder and I need to review their abstracts quickly.
Action:  zotero-cli slr screen --source "Unscreened" --include "Accepted" --exclude "Rejected"
Result:  The TUI launches, displaying the first abstract. Decisions will automatically move items into the Accepted or Rejected folders.
""",
        )
        ScreenCommand.register_args(screen_p)
        screen_p.add_argument("--file", help="Bulk process decisions from CSV")

        decide_p = sub.add_parser(
            "decide",
            help="Record a single screening decision",
            description="Records a single screening decision (Include/Exclude) for an item, updating Screening Database (SDB) notes and optionally moving the item between collections. Ensures traceability of persona, phase, and rationale.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Manually excluding a paper during Abstract Review
Problem: I am reading an abstract and realized it's a survey paper, which violates my inclusion criteria.
Action:  zotero-cli slr decide --key "ABCD1234" --vote "EXCLUDE" --code "EXC02" --reason "Is a survey paper" --phase "title_abstract"
""",
        )
        DecideCommand.register_args(decide_p)

        load_p = sub.add_parser(
            "load",
            help="Bulk-import screening decisions from CSV",
            description="Bulk-imports screening decisions from an external CSV file into your Zotero library. Performs a Matching Phase (Key/DOI) and updates metadata notes. Always run without --force first for a dry-run.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        LoadCommand.register_args(load_p)

        list_p = sub.add_parser(
            "list",
            help="List papers by SLR status (pending, included, excluded)",
            description="Lists items in the SLR funnel based on their status (pending evaluation, accepted/included, or rejected/excluded) and phase.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        ListCommand.register_args(list_p)

        reconcile_p = sub.add_parser(
            "reconcile",
            help="Synchronizes folder locations with audit notes",
            description="Analyzes an SLR tree and automatically moves papers to their correct phase folder based on SDB notes. Enforces exclusive membership.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        ReconcileCommand.register_args(reconcile_p)

        promote_p = sub.add_parser(
            "promote",
            help="Atomic decision and folder displacement",
            description="Records a screening decision (Include/Exclude) and automatically moves the paper into its target phase folder if accepted.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        PromoteCommand.register_args(promote_p)

        # --- Snowballing ---
        snow_p = sub.add_parser(
            "snowball",
            help="Citation tracking (Snowballing) tools",
            description="Executes Forward and Backward Snowballing (citation tracking) to recursively discover new research papers based on a set of seed articles.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        SnowballCommand.register_args(snow_p)

        # --- SDB Maintenance ---
        sdb_p = sub.add_parser(
            "sdb",
            help="Screening DB (SDB) maintenance",
            description="Manages the internal Screening Database (SDB) notes associated with Zotero items, allowing for inspection, modification, or schema migration of the audit trail.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        SDBCommand.register_args(sdb_p)

        # --- Extraction ---
        ext_p = sub.add_parser(
            "extract",
            help="Data Extraction tools",
            description="Systematically extracts research variables, methodologies, and quantitative results from the full text of research papers, optionally using AI agents.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        ExtractionCommand.register_args(ext_p)

        # --- Utilities ---
        prune_p = sub.add_parser(
            "prune",
            help="Enforce mutual exclusivity between two collections",
            description="Removes items from the '--excluded' collection if they already exist in the '--included' collection. Ensures datasets are disjoint for PRISMA reporting.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        prune_p.add_argument(
            "--included", required=True, help="Primary collection (Winner/Included)"
        )
        prune_p.add_argument(
            "--excluded",
            required=True,
            help="Secondary collection (Loser/Excluded - items removed from here)",
        )

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "report":
            SLRReportCommand.execute(gateway, args)
        elif args.verb == "source":
            SLRSourceCommand.execute(gateway, args)
        elif args.verb == "screen":
            if getattr(args, "file", None):
                self._handle_bulk_decide(args)
            else:
                ScreenCommand.execute(args)
        elif args.verb == "decide":
            DecideCommand.execute(args)
        elif args.verb == "load":
            LoadCommand.execute(gateway, args)
        elif args.verb == "list":
            ListCommand.execute(args)
        elif args.verb == "reconcile":
            ReconcileCommand.execute(args)
        elif args.verb == "promote":
            PromoteCommand.execute(args)
        elif args.verb == "prune":
            self._handle_prune(args)
        elif args.verb == "extract":
            ExtractionCommand.execute(args)
        elif args.verb == "sdb":
            SDBCommand.execute(gateway, args)
        elif args.verb == "snowball":
            SnowballCommand.execute(gateway, args)

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
                    target_coll = None
                    if hasattr(args, "include"):
                        target_coll = args.include if vote == "INCLUDE" else args.exclude

                    if service.record_decision(
                        item_key=key,
                        decision=vote,
                        code="bulk",
                        reason=reason,
                        source_collection=args.source if hasattr(args, "source") else None,
                        target_collection=target_coll,
                    ):
                        success_count += 1
                    else:
                        fail_count += 1
            print(f"Done. Success: {success_count}, Failed: {fail_count}")
        except Exception as e:
            print(f"Error processing CSV: {e}")

    def _handle_prune(self, args):
        service = GatewayFactory.get_collection_service(force_user=getattr(args, "user", False))
        print(f"Pruning intersection: '{args.included}' vs '{args.excluded}'...")
        count = service.prune_intersection(args.included, args.excluded)
        if count > 0:
            print(f"[bold green]Pruned {count} items from '{args.excluded}'.")
        else:
            print("No intersection found. Sets are disjoint.")
