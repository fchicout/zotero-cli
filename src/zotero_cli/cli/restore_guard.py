"""`system restore`: its arguments, and what it checks around the restore itself: the library
an archive came from (Issue #659), and the key map it writes afterwards (Issue #721)."""

import argparse
import zipfile
from typing import Any

from zotero_cli import __version__
from zotero_cli.cli.flags import user_flag
from zotero_cli.cli.safety import confirm_other_library
from zotero_cli.core.config import get_config
from zotero_cli.core.exceptions import DataFileError, UsageError, ZoteroCliError
from zotero_cli.core.models import LibraryRef
from zotero_cli.core.services.restore_report import (
    RestoreReport,
    check_key_map_path,
    key_map_document,
    write_key_map,
)
from zotero_cli.core.services.restore_service import archive_library
from zotero_cli.core.utils.terminal_safety import SafeConsole, safe_markup


def print_archive_library(manifest: Any, console: SafeConsole) -> None:
    """The `Library:` line of `system verify`."""
    library = (manifest or {}).get("library") or {}
    if library:
        name = f" ({safe_markup(library['name'])})" if library.get("name") else ""
        console.print(
            f"  - Library: {safe_markup(library.get('type'))} "
            f"{safe_markup(library.get('id'))}{name}"
        )


def check_restore_target(args: argparse.Namespace, dry_run: bool, console: SafeConsole) -> None:
    """An archive from one library is not restored into another by accident: say so in the
    preview, and ask before applying."""
    try:
        source = archive_library(args.file)
    except (OSError, zipfile.BadZipFile, KeyError, DataFileError):
        return  # unreadable: the restore itself reports why, as it always did
    if source is None:  # an archive from before 1.2 does not say where it came from
        return
    library_id, library_type = get_config(args.config).resolve_library_target(user_flag(args))
    target = LibraryRef(library_type, str(library_id))
    if source.same_as(target):
        return
    console.print(
        f"[bold yellow]Warning:[/bold yellow] this archive was taken from "
        f"{safe_markup(source.type)} library {safe_markup(source.id)}, but it would be "
        f"restored into {safe_markup(target.type)} library {safe_markup(target.id)}."
    )
    if not dry_run and not confirm_other_library(
        "Restore into this other library?", getattr(args, "yes", False)
    ):
        raise UsageError("restore cancelled: nothing was written.")


def add_restore_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Restore
    restore_p = sub.add_parser(
        "restore",
        help="Restore from a .zaf backup",
        description="Reconstructs an entire Zotero library or specific collections from a previously created Zotero Archive Format (.zaf) file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Recovering from an accidental library deletion
Problem: I've accidentally deleted a large set of folders in Zotero and I need to restore them from last week's backup.
Action:  zotero-cli system restore --file "backup_2024_01_01.zaf" --dry-run
Result:  The CLI shows exactly which items and folders will be recreated.

Scenario: Applying a restore after reviewing the plan
Problem: I've checked the dry-run output and I'm ready to actually restore.
Action:  zotero-cli system restore --file "backup_2024_01_01.zaf" --execute
Result:  The archive is restored into the library.

Scenario: Following the items to their new keys
Problem: My notes and scripts refer to items by key, and a restore gives new keys to what it creates.
Action:  zotero-cli system restore --file "backup_2024_01_01.zaf" --execute --key-map keys.json
Result:  keys.json says, for every archived item, collection and search, its key in the library now.

Notes
-----
• Common Failure Modes: Attempting to restore a .zaf file that is corrupted or from a different account context.
• Safety Tips: ALWAYS run with --dry-run first to understand the impact.
• Previews by default: nothing is written to your library until you pass --execute.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/system_restore.md
""",
    )
    restore_p.add_argument("--file", required=True, help="Input .zaf file")
    restore_mode = restore_p.add_mutually_exclusive_group()
    restore_mode.add_argument("--dry-run", action="store_true", help="Simulate restore")
    restore_mode.add_argument(
        "--execute",
        action="store_true",
        help="Apply the restore (without it, only a preview is shown)",
    )
    restore_p.add_argument(
        "--yes",
        action="store_true",
        help="Do not ask before restoring into a different library than the archive came from",
    )
    restore_p.add_argument(
        "--key-map",
        metavar="FILE",
        help="With --execute: write the new key of every restored item, collection and saved "
        "search to this JSON file",
    )


def check_key_map_request(args: argparse.Namespace, dry_run: bool) -> None:
    """Refuses, before anything is restored, a key map that could not be produced."""
    path = getattr(args, "key_map", None)
    if not path:
        return
    if dry_run:
        raise UsageError(
            "--key-map needs --execute: a preview creates nothing, so there are no new keys "
            "to report."
        )
    check_key_map_path(path, args.file)


def save_key_map(args: argparse.Namespace, report: RestoreReport, console: SafeConsole) -> None:
    """Writes the key map when one was asked for, also after a restore with errors: a partial
    restore is when the new keys matter most."""
    path = getattr(args, "key_map", None)
    if not path:
        return
    try:
        write_key_map(path, key_map_document(report, f"zotero-cli {__version__}"))
    except OSError as e:
        raise ZoteroCliError(
            f"The restore ran (see above), but its key map could not be written to {path}: {e}"
        ) from e
    console.print(f"Key map written to [green]{safe_markup(path)}[/green]")
