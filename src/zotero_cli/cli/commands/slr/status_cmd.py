import argparse
from typing import Any, Dict

from rich.console import Console
from rich.table import Table

from zotero_cli.infra.factory import GatewayFactory

console = Console()


class StatusCommand:
    """
    CLI command to display SLR progress across raw_* collections.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.description = (
            "Displays a quantitative summary of the SLR funnel across all raw_* sources."
        )

    @staticmethod
    def execute(args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_slr_status_service(force_user=force_user)

        with console.status("[bold green]Scanning SLR Hierarchy..."):
            statuses = service.get_slr_status()

        if not statuses:
            console.print("[yellow]No raw_* collections found in the library.[/yellow]")
            return

        table = Table(title="SLR Progress Status", show_header=True, header_style="bold magenta")
        table.add_column("Source Collection")
        table.add_column("Tree Total", justify="right", style="bold yellow")
        table.add_column("1-T&A (Acc/Rej/Pen)", justify="center")
        table.add_column("2-FT (Acc/Rej/Pen)", justify="center")
        table.add_column("3-QA (Acc/Rej/Pen)", justify="center")
        table.add_column("4-DE (Extracted)", justify="center", style="blue")

        totals: Dict[str, Any] = {
            "tree_total": 0,
            "title_abstract": {"accepted": 0, "rejected": 0, "pending": 0},
            "full_text": {"accepted": 0, "rejected": 0, "pending": 0},
            "quality_assessment": {"accepted": 0, "rejected": 0, "pending": 0},
            "data_extraction": {"accepted": 0},
        }

        for s in statuses:
            totals["tree_total"] += s.total_unique

            def fmt(phase_id):
                stats = s.phases.get(phase_id)
                if not stats:
                    return "-"
                totals[phase_id]["accepted"] += stats.accepted
                totals[phase_id]["rejected"] += stats.rejected
                totals[phase_id]["pending"] += stats.pending
                base = f"[green]{stats.accepted}[/green]/[orange_red1]{stats.rejected}[/orange_red1]/[yellow]{stats.pending}[/yellow]"
                return f"{base} ✅" if stats.pending == 0 else base

            de_stats = s.phases.get("data_extraction")
            if de_stats:
                totals["data_extraction"]["accepted"] += de_stats.accepted

            table.add_row(
                f"[bold cyan]{s.source_name}[/bold cyan] ({s.source_key})",
                str(s.total_unique),
                fmt("title_abstract"),
                fmt("full_text"),
                fmt("quality_assessment"),
                f"[bold blue]{de_stats.accepted}[/bold blue]" if de_stats else "-",
            )

        def fmt_total(phase_id):
            p_stats = totals[phase_id]
            base = f"[bold green]{p_stats['accepted']}[/bold green]/[bold orange_red1]{p_stats['rejected']}[/bold orange_red1]/[bold yellow]{p_stats['pending']}[/bold yellow]"
            return f"{base} ✅" if p_stats["pending"] == 0 else base

        table.add_section()
        table.add_row(
            "[bold yellow]TOTAL (SUM)[/bold yellow]",
            f"[bold yellow]{totals['tree_total']}[/bold yellow]",
            fmt_total("title_abstract"),
            fmt_total("full_text"),
            fmt_total("quality_assessment"),
            f"[bold blue]{totals['data_extraction']['accepted']}[/bold blue]",
        )
        console.print(table)
