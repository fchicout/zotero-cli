"""The systematic-review commands leave zotero-cli in 4.0.0 (Issue #541).

They keep working in 3.x, but each run of one prints a single warning on stderr
(stdout stays clean for scripts), and `zotero-cli schema` marks them. Applications
that build on zotero-cli take over the workflow; the library-management commands
are not affected.
"""

import argparse
import sys
from typing import Dict, Optional, Sequence

REMOVAL_VERSION = "4.0.0"
TRACKER_URL = "https://github.com/fchicout/zotero-cli/issues/541"

# Command paths (a prefix is enough) that are removed in REMOVAL_VERSION.
DEPRECATED_COMMANDS = (("slr",), ("report", "verify-latex"))


def is_deprecated(path: Sequence[str]) -> bool:
    """Whether the command at `path` (e.g. ["slr", "list", "pending"]) is deprecated."""
    return any(tuple(path[: len(prefix)]) == prefix for prefix in DEPRECATED_COMMANDS)


def schema_marker(path: Sequence[str]) -> Optional[Dict[str, str]]:
    """The `deprecated` entry `zotero-cli schema` shows for a command, or None."""
    return {"removed_in": REMOVAL_VERSION, "see": TRACKER_URL} if is_deprecated(path) else None


def _path_of(args: argparse.Namespace) -> Sequence[str]:
    command = getattr(args, "command", None)
    if command == "report":
        return ("report", str(getattr(args, "report_type", "")))
    return (str(command),) if command else ()


def warn_deprecated_command(args: argparse.Namespace) -> None:
    """Prints the one-line warning if the command being run is deprecated."""
    path = _path_of(args)
    if not is_deprecated(path):
        return
    name = " ".join(("zotero-cli", *(path if path[0] != "slr" else path[:1])))
    print(
        f"Warning: `{name}` is deprecated and will be removed in {REMOVAL_VERSION}: the "
        "systematic-review workflow is moving out of zotero-cli, into applications built on "
        "it. Notes already in your library are not changed. "
        f"See {TRACKER_URL}.",
        file=sys.stderr,
    )
