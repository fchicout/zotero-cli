"""
The confirmation rule for commands that permanently delete (Issue #378):

- they preview by default and act only with `--execute`;
- with `--execute` they still ask for confirmation, unless `--yes` is given;
- without a terminal to ask on (scripts, CI, agents), they refuse unless
  `--yes` is given, instead of failing on EOF or guessing.

Commands that only remove items from a collection (the items stay in the
library) need `--execute` but no confirmation.
"""

import sys

from rich.prompt import Confirm


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
