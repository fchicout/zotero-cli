import argparse
import sys

from rich.markup import escape
from rich.table import Table

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.infra.factory import GatewayFactory

console = Console()


class LoadCommand:
    @staticmethod
    def register_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--file",
            required=True,
            help="Path to the input CSV file. Must contain a 'Key' or 'DOI' column.",
        )
        parser.add_argument(
            "--reviewer",
            required=True,
            help="Reviewer persona/name (e.g., 'Chicout') for audit tracking.",
        )
        parser.add_argument(
            "--phase",
            default="title_abstract",
            help="Review phase identifier (e.g., 'title_abstract', 'full_text').",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Apply the changes to the Zotero library (default: preview only).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Deprecated alias of --execute; will be removed in a future release.",
        )
        # Column mapping
        parser.add_argument("--col-key", help="CSV column mapping for Zotero Key (Default: 'Key').")
        parser.add_argument(
            "--col-vote",
            help="CSV column mapping for Decision/Vote (Default: 'Vote'). Expected: INCLUDE/EXCLUDE.",
        )
        parser.add_argument(
            "--col-reason",
            help="CSV column mapping for the Reason for decision (Default: 'Reason').",
        )
        parser.add_argument(
            "--col-code", help="CSV column mapping for Exclusion Code (Default: 'Code')."
        )
        parser.add_argument(
            "--col-doi",
            help="CSV column mapping for DOI (Default: 'DOI'). Used for matching if Key is missing.",
        )
        parser.add_argument(
            "--col-title",
            help="CSV column mapping for Item Title (Default: 'Title'). Used as a secondary anchor.",
        )
        parser.add_argument(
            "--col-evidence",
            help="CSV column mapping for Evidence or snippets (Default: 'Evidence').",
        )
        parser.add_argument(
            "--move-to-included",
            help="Target collection for items with an 'INCLUDE' or 'ACCEPTED' decision.",
        )
        parser.add_argument(
            "--move-to-excluded",
            help="Target collection for items with an 'EXCLUDE' or 'REJECTED' decision.",
        )

    @staticmethod
    def execute(gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        service = GatewayFactory.get_csv_inbound_service(force_user=getattr(args, "user", False))
        # Elsewhere --force means "skip the confirmation"; here it used to mean
        # "apply". It still applies, so existing scripts don't silently become
        # dry runs, but it's deprecated in favour of --execute (Issue #378).
        apply = bool(getattr(args, "execute", False) or args.force)
        if args.force and not getattr(args, "execute", False):
            print(
                "Warning: `slr load --force` is deprecated; use --execute to apply changes.",
                file=sys.stderr,
            )
        dry_run = not apply

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

        col_service = GatewayFactory.get_collection_service(force_user=getattr(args, "user", False))
        results = service.enrich_from_csv(
            csv_path=args.file,
            reviewer=args.reviewer,
            dry_run=dry_run,
            force=apply,
            phase=args.phase,
            column_map=column_map,
            move_to_included=args.move_to_included,
            move_to_excluded=args.move_to_excluded,
            collection_service=col_service,
        )

        if "error" in results:
            console.print(f"[bold red]Error:[/bold red] {escape(results['error'])}")
            return

        table = Table(title="Import CSV Results")
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        table.add_row("Total Rows", str(results["total_rows"]))
        table.add_row("Matched Items", f"[green]{results['matched']}[/]")
        table.add_row("Unmatched Rows", f"[red]{len(results['unmatched'])}[/]")
        table.add_row("Notes Updated", str(results.get("updated", 0)))
        table.add_row("Notes Created", str(results.get("created", 0)))
        table.add_row("Skipped (Dry Run)", str(results.get("skipped", 0)))
        console.print(table)
        if dry_run:
            console.print(
                "[yellow]Preview only - nothing was changed. "
                "Re-run with --execute to apply.[/yellow]"
            )
