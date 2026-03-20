import argparse
from rich.console import Console
from rich.table import Table

from zotero_cli.infra.factory import GatewayFactory

console = Console()

class LoadCommand:
    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.add_argument("--file", required=True, help="Input CSV path")
        parser.add_argument("--reviewer", required=True, help="Reviewer persona/name")
        parser.add_argument("--phase", default="title_abstract", help="Review phase")
        parser.add_argument("--force", action="store_true", help="Apply changes (not dry-run)")
        # Column mapping
        parser.add_argument("--col-key", help="CSV column for Zotero Key (Default: Key)")
        parser.add_argument("--col-vote", help="CSV column for Decision (Default: Vote)")
        parser.add_argument("--col-reason", help="CSV column for Reason (Default: Reason)")
        parser.add_argument("--col-code", help="CSV column for Exclusion Code (Default: Code)")
        parser.add_argument("--col-doi", help="CSV column for DOI (Default: DOI)")
        parser.add_argument("--col-title", help="CSV column for Title (Default: Title)")
        parser.add_argument("--col-evidence", help="CSV column for Evidence (Default: Evidence)")
        parser.add_argument(
            "--move-to-included", help="Target collection for items with INCLUDE/ACCEPTED decision"
        )
        parser.add_argument(
            "--move-to-excluded", help="Target collection for items with EXCLUDE/REJECTED decision"
        )

    @staticmethod
    def execute(gateway, args: argparse.Namespace):
        service = GatewayFactory.get_csv_inbound_service(force_user=getattr(args, "user", False))
        dry_run = not args.force

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
            force=args.force,
            phase=args.phase,
            column_map=column_map,
            move_to_included=args.move_to_included,
            move_to_excluded=args.move_to_excluded,
            collection_service=col_service,
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
        table.add_row("Notes Updated", str(results.get("updated", 0)))
        table.add_row("Notes Created", str(results.get("created", 0)))
        table.add_row("Skipped (Dry Run)", str(results.get("skipped", 0)))
        console.print(table)
