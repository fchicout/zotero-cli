"""
The confirmation rule for commands that permanently delete (Issue #378):

- they preview by default and act only with `--execute`;
- with `--execute` they still ask for confirmation, unless `--yes` is given;
- without a terminal to ask on (scripts, CI, agents), they refuse unless
  `--yes` is given, instead of failing on EOF or guessing.

Commands that only remove items from a collection (the items stay in the
library) need `--execute` but no confirmation.
"""

import argparse
import sys

from rich.prompt import Confirm

from zotero_cli.core.exceptions import UsageError


def confirm_destructive(question: str, assume_yes: bool) -> bool:
    """True if the destructive action may go ahead. Exits with status 2 when
    there's no terminal to ask on and `--yes` wasn't given."""
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(
            "Refusing to delete without confirmation: no terminal to ask on. "
            "Pass --yes to confirm non-interactively.",
            file=sys.stderr,
        )
        sys.exit(2)
    return bool(Confirm.ask(question, default=False))


def preview_notice(what: str) -> str:
    """The standard closing line of a preview."""
    return f"[yellow]Preview only - nothing was changed. Re-run with --execute to {what}.[/yellow]"


def warn_default_apply(command: str) -> None:
    """For a command that predates this policy and still applies its changes
    by default in 3.x (Issue #378: `item delete`, `storage checkout`,
    `system restore`) - printed once when neither `--dry-run` nor `--execute`
    was given, so a script written before these flags existed keeps working
    unchanged but is told what to add. `command` switches to preview-by-
    default in 4.0 (Issue #462), when this warning is removed."""
    print(
        f"Warning: `{command}` currently applies its changes by default; pass --execute "
        "explicitly, or --dry-run to preview first. This will change to preview-by-default "
        "in 4.0.",
        file=sys.stderr,
    )


def add_permanent_flag(parser: argparse.ArgumentParser, what: str) -> None:
    """`--permanent`, the explicit spelling of what a delete does today: remove
    `what` for good instead of moving it to Zotero's trash (Issue #402). Trashing
    becomes the default in 4.0 (Issue #462); passing `--permanent` now keeps
    permanent deletion then, and silences the warning."""
    parser.add_argument(
        "--permanent",
        action="store_true",
        help=f"Delete {what} permanently (what happens today without --trash). Moving to the "
        "trash becomes the default in 4.0, so pass this to keep deleting for good",
    )


def resolve_trash(args: argparse.Namespace, command: str, *, applying: bool) -> bool:
    """Whether a delete goes to the trash. In 3.x that is `--trash`; with neither
    `--trash` nor `--permanent`, a delete that is really applied warns once that
    4.0 trashes by default (Issue #402), then stays permanent so scripts keep
    working. Both flags together are a usage error."""
    trash = getattr(args, "trash", False) is True
    permanent = getattr(args, "permanent", False) is True
    if trash and permanent:
        raise UsageError("--trash and --permanent contradict each other: pass one.")
    if applying and not trash and not permanent:
        print(
            f"Warning: `{command}` currently deletes permanently by default; pass --trash to "
            "move to Zotero's trash (recoverable), or --permanent to keep deleting for good. "
            "In 4.0 it will move to the trash by default.",
            file=sys.stderr,
        )
    return trash
