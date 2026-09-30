"""Output formats for record-shaped results (Issues #323, #380).

A result is a list of flat records (dicts) plus the ordered columns to show.
`item list` and every other list-style command render through here, so
`--format json|csv|markdown` means the same thing everywhere: JSON is a list
of objects, CSV and Markdown carry one row per record, and stdout holds
nothing but the data (progress and notices belong on stderr).
"""

import csv
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, TextIO

from rich.table import Table
from rich.text import Text

from zotero_cli.core.utils.csv_safety import sanitize_csv_row
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup, strip_controls

FORMATS = ["table", "json", "csv"]

Record = Mapping[str, Any]  # values: str/int/float, or a list of them


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    style: Optional[str] = None
    justify: str = "left"


def flat(value: Any) -> str:
    """One cell as text, with terminal control characters removed: CSV and
    Markdown go straight to the terminal, and item fields are settable by
    any library collaborator (GHSA-3r38-p632-f79q)."""
    if isinstance(value, list):
        return strip_controls("; ".join(str(v) for v in value))
    return strip_controls("" if value is None else str(value))


def md_cell(value: Any) -> str:
    return flat(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_table(
    records: Sequence[Record],
    columns: Sequence[Column],
    title: str,
    console: Console,
    footer: Optional[str] = None,
) -> None:
    table = Table(title=title)
    for col in columns:
        table.add_column(col.label, style=col.style, justify=col.justify)  # type: ignore[arg-type]
    for record in records:
        # Text(), not a plain str: a title like "[Retracted] ..." must render
        # literally rather than be parsed as Rich markup (Issue #253).
        table.add_row(*(Text(flat(record.get(c.key, ""))) for c in columns))
    console.print(table)
    if footer:
        console.print(f"\n[dim]{safe_markup(footer)}[/dim]")


def render_json(records: Sequence[Record], columns: Sequence[Column], out: TextIO) -> None:
    rows: List[Dict[str, Any]] = [{c.key: r.get(c.key, "") for c in columns} for r in records]
    out.write(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")


def render_csv(records: Sequence[Record], columns: Sequence[Column], out: TextIO) -> None:
    writer = csv.writer(out)
    writer.writerow([c.key for c in columns])
    for record in records:
        # Fields are settable by any library collaborator - guard against
        # spreadsheet formula injection (Issue #237).
        writer.writerow(sanitize_csv_row([flat(record.get(c.key, "")) for c in columns]))


def render_markdown(records: Sequence[Record], columns: Sequence[Column], out: TextIO) -> None:
    lines = [
        "| " + " | ".join(c.label for c in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for record in records:
        lines.append("| " + " | ".join(md_cell(record.get(c.key, "")) for c in columns) + " |")
    out.write("\n".join(lines) + "\n")


def render_data(
    records: Sequence[Record],
    columns: Sequence[Column],
    fmt: str,
    out: Optional[TextIO] = None,
) -> None:
    """json, csv or markdown to `out` (stdout by default). `table` is the
    caller's to draw, since each command has its own title and footer."""
    stream = out or sys.stdout
    {"json": render_json, "csv": render_csv, "markdown": render_markdown}[fmt](
        records, columns, stream
    )
