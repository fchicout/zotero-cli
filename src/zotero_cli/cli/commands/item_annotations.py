"""`item annotations`: the PDF highlights and notes of an item (Issue #558)."""

import argparse
from typing import List

from zotero_cli.cli.flags import (
    LIST_FORMAT_HELP,
    LIST_FORMATS,
    add_format_flag,
    add_key_argument,
    resolve_key,
)
from zotero_cli.cli.presenters import records
from zotero_cli.core import annotations as annotation_records
from zotero_cli.core.exceptions import NotFound
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console

EPILOG = """
Examples
--------
Scenario: Pulling my highlights out of a paper
Problem: I highlighted and commented a PDF in Zotero and want the text in my notes.
Action:  zotero-cli item annotations ABCD1234
Result:  A table of the item's annotations in reading order: page, type, the highlighted text and my comment.

Scenario: Only the highlights, for a script
Action:  zotero-cli item annotations --key ABCD1234 --type highlight --format json
Result:  A JSON list on stdout: key, attachment, type, text, comment, color, page, tags, date_added.

Scenario: The same, offline
Action:  zotero-cli --offline item annotations --key ABCD1234
Result:  The annotations are read from the local zotero.sqlite, with no network.

Notes
-----
• The key can be a regular item (its PDF attachments are searched) or a PDF attachment itself.
• Common Failure Modes: an item with no PDF, or a PDF you haven't annotated, prints "No annotations found" (exit 0, an empty list in the data formats); an unknown key exits 3.
• Safety Tips: read-only. Annotation text comes from the PDF and is shown as plain text.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_annotations.md
"""

COLUMNS = [
    records.Column("page", "Page", justify="right"),
    records.Column("type", "Type", style="cyan"),
    records.Column("text", "Text"),
    records.Column("comment", "Comment"),
    records.Column("tags", "Tags"),
    records.Column("key", "Key", style="dim"),
    records.Column("attachment", "Attachment", style="dim"),
    records.Column("color", "Color"),
    records.Column("date_added", "Added"),
]
# What the table shows; the data formats carry every column.
TABLE_COLUMNS = COLUMNS[:6]


def register_args(parser: argparse.ArgumentParser) -> None:
    add_key_argument(parser, "Item key (a regular item, or a PDF attachment)")
    parser.add_argument(
        "--type",
        dest="annotation_type",
        action="append",
        choices=list(annotation_records.TYPES),
        help="Only this kind of annotation; repeat for several (default: all)",
    )
    add_format_flag(parser, choices=LIST_FORMATS, help=LIST_FORMAT_HELP)


def run(gateway: ZoteroGateway, args: argparse.Namespace) -> None:
    resolve_key(args)
    fmt = getattr(args, "format", "table")
    if gateway.get_item(args.key) is None:
        raise NotFound(f"Item '{args.key}' not found.")

    wanted = set(getattr(args, "annotation_type", None) or [])
    found: List[annotation_records.Annotation] = [
        a for a in gateway.get_annotations(args.key) if not wanted or a["type"] in wanted
    ]

    if fmt != "table":
        records.render_data(found, COLUMNS, fmt)
        return

    console = Console()
    if not found:
        console.print("[yellow]No annotations found.[/yellow]")
        return
    records.render_table(found, TABLE_COLUMNS, f"Annotations ({len(found)})", console)
