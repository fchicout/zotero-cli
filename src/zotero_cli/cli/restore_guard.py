"""The checks `system restore` makes about the library an archive came from (Issue #659)."""

import argparse
import zipfile
from typing import Any

from zotero_cli.cli.flags import user_flag
from zotero_cli.cli.safety import confirm_other_library
from zotero_cli.core.config import get_config
from zotero_cli.core.exceptions import DataFileError, UsageError
from zotero_cli.core.models import LibraryRef
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
