import argparse
from typing import List, Optional

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.merge_service import MergePlan
from zotero_cli.core.services.sdb.sdb_service import SDB_STATUS_CONFLICTING
from zotero_cli.core.services.slr.dedupe_service import ClassifiedDuplicateGroup
from zotero_cli.infra.factory import GatewayFactory

console = Console()

STATUS_COLOR = {"MATCHING": "green", "CONFLICTING": "red", "UNSCREENED": "yellow"}


class DedupeCommand:
    """
    Subcommand implementing `slr dedupe`: SLR-specific duplicate
    reconciliation on top of the generic `report duplicates`/`item merge`
    primitives.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser) -> None:
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.description = (
            "Detects duplicate items across the SLR source tree (or a given set of "
            "collections), classifies each group by whether existing SDB screening "
            "decisions agree (MATCHING/CONFLICTING/UNSCREENED), and auto-merges the "
            "safe cases. Conflicting groups are left for manual review."
        )
        parser.epilog = """
Scenario-Based Examples
-----------------------
Scenario: Reviewing SLR-wide duplicates before merging anything
Problem: I want to see how many duplicate groups exist across my whole SLR tree, and which are safe to auto-merge.
Action:  zotero-cli slr dedupe
Result:  A table lists every duplicate group with its SDB status; MATCHING/UNSCREENED groups are marked
         auto-resolvable, CONFLICTING groups are flagged for manual review. Nothing is written.

Scenario: Auto-merging the safe duplicates, SLR-wide
Problem: I've reviewed the preview and want to consolidate the MATCHING/UNSCREENED groups now.
Action:  zotero-cli slr dedupe --execute
Result:  MATCHING/UNSCREENED groups are merged (tags/collections unioned, notes/attachments moved,
         duplicates permanently deleted) with a richer SDB reconciliation note recording each folded
         occurrence's prior screening decisions and source collection. CONFLICTING groups are untouched.

Scenario: Resolving conflicting groups by hand
Problem: Some duplicate groups have genuinely conflicting screening decisions across sources and need a human call.
Action:  zotero-cli slr dedupe --export-plan slr_dedupe_plan.csv
Result:  A CSV is written with one row per occurrence; MATCHING/UNSCREENED rows already have role/reason
         filled in, CONFLICTING rows are blank. Fill those in, then run
         `zotero-cli item merge --from-plan slr_dedupe_plan.csv --execute`.
"""
        parser.add_argument(
            "--sources",
            help="Comma-separated collection names or keys to scope detection to. "
            "Omit to scan the entire SLR source tree (every raw_* collection and its phase subfolders).",
        )
        parser.add_argument(
            "--export-plan",
            help="Optional path (.csv or .json) to export the full reconciliation plan, "
            "including blank CONFLICTING rows, for manual resolution via `item merge --from-plan`.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Merge the auto-resolved (MATCHING/UNSCREENED) groups. CONFLICTING groups are never auto-merged.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip the interactive confirmation prompt (still requires --execute).",
        )

    @staticmethod
    def execute(gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_slr_dedupe_service(force_user=force_user)

        scope: Optional[List[str]] = None
        if args.sources:
            scope = []
            for name in args.sources.split(","):
                name = name.strip()
                cid = gateway.get_collection_id_by_name(name) or name
                scope.append(cid)

        groups = service.find_and_classify(scope)
        for warning in service.warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")

        if not groups:
            console.print("[green]No duplicates found.[/green]")
            return

        DedupeCommand._print_preview(groups)

        plan = service.build_reconciliation_plan(groups)
        resolved_entries = [e for e in plan.entries if e.decision is not None]
        conflicting_count = sum(1 for g in groups if g.sdb_status == SDB_STATUS_CONFLICTING)

        if args.export_plan:
            from zotero_cli.core.services.merge_plan_io import (
                serialize_plan_to_csv,
                serialize_plan_to_json,
            )

            content = (
                serialize_plan_to_json(plan)
                if args.export_plan.lower().endswith(".json")
                else serialize_plan_to_csv(plan)
            )
            with open(args.export_plan, "w", newline="", encoding="utf-8") as f:
                f.write(content)
            console.print(f"[green]Exported reconciliation plan to {args.export_plan}[/green]")

        if not args.execute:
            console.print(
                f"\n[cyan]{len(resolved_entries)} group(s) auto-resolvable, "
                f"{conflicting_count} group(s) need manual review.[/cyan] "
                "Pass --execute to merge the resolvable ones."
            )
            return

        if not resolved_entries:
            console.print(
                "[yellow]No auto-resolvable groups to merge (all groups are CONFLICTING).[/yellow]"
            )
            return

        resolved_plan = MergePlan(entries=resolved_entries)
        preview = service.execute_reconciliation(resolved_plan, dry_run=True)
        merge_count = sum(len(r.merged_keys) for r in preview.group_results)
        console.print(
            f"\n[bold]About to merge {len(resolved_entries)} group(s), "
            f"permanently deleting {merge_count} duplicate item(s).[/bold]"
        )

        if not args.force and not Confirm.ask("Proceed?"):
            console.print("[yellow]Aborted. Nothing written.[/yellow]")
            return

        result = service.execute_reconciliation(resolved_plan, dry_run=False)
        merged = sum(len(r.merged_keys) for r in result.group_results if r.success)
        failed = [r for r in result.group_results if not r.success]
        console.print(
            f"[bold green]Merged {merged} duplicate item(s) across {len(resolved_entries)} group(s).[/bold green]"
        )
        for r in failed:
            console.print(f"[red]Failed to merge into '{r.master_key}': {', '.join(r.errors)}[/red]")

        if conflicting_count:
            console.print(
                f"\n[yellow]{conflicting_count} group(s) still need manual review "
                "(conflicting SDB decisions) - use --export-plan to resolve them.[/yellow]"
            )

    @staticmethod
    def _print_preview(groups: List[ClassifiedDuplicateGroup]) -> None:
        table = Table(title="SLR Duplicate Reconciliation")
        table.add_column("Match Type")
        table.add_column("Identifier")
        table.add_column("SDB Status")
        table.add_column("Occurrences", justify="right")
        table.add_column("Resolution")
        for g in groups:
            color = STATUS_COLOR.get(g.sdb_status, "white")
            resolution = "NEEDS REVIEW" if g.sdb_status == SDB_STATUS_CONFLICTING else "AUTO-MERGE"
            table.add_row(
                g.match_type,
                g.identifier,
                f"[{color}]{g.sdb_status}[/{color}]",
                str(len(g.occurrences)),
                resolution,
            )
        console.print(table)
