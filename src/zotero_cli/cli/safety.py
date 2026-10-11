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


def add_permanent_flag(parser: argparse.ArgumentParser, what: str) -> None:
    """`--permanent` (Issue #402): remove `what` for good instead of moving it to
    Zotero's trash, which is the default since 4.0 (Issue #462)."""
    parser.add_argument(
        "--permanent",
        action="store_true",
        help=f"Delete {what} for good instead of moving it to Zotero's trash (not recoverable)",
    )


def resolve_trash(args: argparse.Namespace) -> bool:
    """Whether a delete goes to Zotero's trash: yes, unless `--permanent`. `--trash`
    is the default and stays accepted for scripts written before 4.0; giving it
    together with `--permanent` is a usage error."""
    if getattr(args, "trash", False) is True and getattr(args, "permanent", False) is True:
        raise UsageError("--trash and --permanent contradict each other: pass one.")
    return getattr(args, "permanent", False) is not True
