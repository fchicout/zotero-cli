import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from zotero_cli.core.services.slr.integrity import IntegrityService
from zotero_cli.infra.factory import GatewayFactory

console = Console()

class VerifyCommand:
    """
    Unified verification for SLR collections and manuscripts.
    """
    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.add_argument("--collection", help="Verify metadata completeness for a collection")
        parser.add_argument("--latex", help="Verify citations in a LaTeX manuscript")
        parser.add_argument("--verbose", action="store_true", help="Show detailed failure logs")
        parser.add_argument(
            "--export-missing", help="Path to export keys of missing items (for --collection)"
        )

    @staticmethod
    def execute(gateway, args: argparse.Namespace):
        if args.latex:
            VerifyCommand._verify_latex(args)
        elif args.collection:
            VerifyCommand._verify_collection(gateway, args)
        else:
            console.print("[red]Error: Specify --collection or --latex for verification.[/red]")

    @staticmethod
    def _verify_latex(args):
        service = GatewayFactory.get_audit_service(force_user=getattr(args, "user", False))
        with console.status(f"[bold green]Verifying LaTeX manuscript: {args.latex}..."):
            report = service.audit_manuscript(Path(args.latex))

        console.print(f"\n[bold]SLR LaTeX Verification for:[/bold] [cyan]{args.latex}[/cyan]")
        console.print(f"Total unique citations found: {report['total_citations']}")

        if not report["items"]:
            console.print("[yellow]No citations found in the manuscript.[/yellow]")
            return

        table = Table(title="Citation Verification Results")
        table.add_column("Key", style="dim")
        table.add_column("Status")
        table.add_column("Decision")
        table.add_column("Title")

        errors = 0
        unscreened = 0

        for key, data in report["items"].items():
            status = "[green]OK[/green]"
            decision = data.get("decision", "-")

            if not data["exists"]:
                status = "[red]MISSING[/red]"
                errors += 1
            elif not data["screened"]:
                status = "[yellow]UNSCREENED[/yellow]"
                unscreened += 1

            table.add_row(
                key,
                status,
                decision or "-",
                (data.get("title") or "")[:50] + ("..." if len(data.get("title", "")) > 50 else ""),
            )

        console.print(table)

        if errors > 0 or unscreened > 0:
            console.print(
                f"\n[bold red]Verification Failed:[/bold red] {errors} missing from library, {unscreened} unscreened in SLR."
            )
            sys.exit(1)
        else:
            console.print("\n[bold green]Verification Success:[/] All citations are verified and screened.")

    @staticmethod
    def _verify_collection(gateway, args: argparse.Namespace):
        service = IntegrityService(gateway)
        print(f"Auditing collection: {args.collection}...")
        report = service.audit_collection(args.collection)

        if not report:
            sys.exit(1)

        table = Table(title=f"Collection Verification: {args.collection}")
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

        if args.export_missing:
            missing_keys = set()
            for item in report.items_missing_id:
                missing_keys.add(item.key)
            for item in report.items_missing_pdf:
                missing_keys.add(item.key)

            if missing_keys:
                with open(args.export_missing, "w", encoding="utf-8") as f:
                    for key in sorted(list(missing_keys)):
                        f.write(f"{key}\n")
                console.print(
                    f"[green]Exported {len(missing_keys)} missing item keys to {args.export_missing}[/green]"
                )
            else:
                console.print("[yellow]No missing items found to export.[/yellow]")

        if has_failures:
            print("\n[bold red]Verification FAILED.[/bold red] Some items are not submission-ready.")
            sys.exit(1)
        else:
            print("\n[bold green]Verification PASSED.[/bold green] All items are submission-ready.")
