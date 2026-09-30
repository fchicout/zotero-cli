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
