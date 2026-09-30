"""Shared argparse helpers for flags that more than one command defines."""

import argparse
import sys
from typing import Any, Sequence


class _DeprecatedVerbose(argparse.Action):
    """The old per-command `--verbose`: still works (stores to `details`, so
    it doesn't touch the global `-v`), but warns and points at `--details`."""

    def __init__(self, option_strings: Sequence[str], dest: str, **kwargs: Any) -> None:
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        print(
            "Warning: `--verbose` on this command is deprecated; use --details "
            "(the global `-v` is what turns on debug logging). Removed in 4.0.",
            file=sys.stderr,
        )
        setattr(namespace, self.dest, True)


def add_details_flag(parser: argparse.ArgumentParser, help: str) -> None:
    """`--details` (Issue #374), plus a hidden `--verbose` alias for scripts
    written before the rename. Both store to `details`: the global `-v`
    owns the `verbose` dest, and a subcommand flag with that dest would
    reset it."""
    parser.add_argument("--details", action="store_true", help=help)
    parser.add_argument(
        "--verbose",
        action=_DeprecatedVerbose,
        dest="details",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
