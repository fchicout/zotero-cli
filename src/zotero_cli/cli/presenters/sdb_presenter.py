"""Terminal rendering of SDB audit entries (kept out of the domain layer, Issue #393)."""

from typing import Any, Dict, List

from rich.table import Table

from zotero_cli.core.utils.terminal_safety import safe_markup


def build_inspect_table(item_key: str, entries: List[Dict[str, Any]]) -> Table:
    table = Table(title=f"SDB Inspect: {item_key}")
    table.add_column("Decision")
    table.add_column("Criteria/Reason")
    table.add_column("Persona", style="cyan")
    table.add_column("Phase", style="magenta")
    table.add_column("Timestamp", style="dim")
    table.add_column("Version", style="dim")

    for e in entries:
        decision = e.get("decision", "N/A")
        color = "green" if decision == "accepted" else "red"

        reason = ", ".join(e.get("reason_code", []))
        if e.get("reason_text"):
            reason += f" ({e['reason_text'][:30]}...)"

        table.add_row(
            f"[{color}]{safe_markup(decision)}[/{color}]",
            reason,
            e.get("persona", "N/A"),
            e.get("phase", "N/A"),
            e.get("timestamp", "N/A"),
            e.get("audit_version", "N/A"),
        )

    return table
