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


class _DeprecatedAlias(argparse.Action):
    """An old spelling of a flag: stores its value like the new one, but
    warns and names the replacement."""

    def __init__(
        self, option_strings: Sequence[str], dest: str, replacement: str = "", **kwargs: Any
    ) -> None:
        self.replacement = replacement
        super().__init__(option_strings, dest, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        print(
            f"Warning: `{option_string}` is deprecated; use {self.replacement}. Removed in 4.0.",
            file=sys.stderr,
        )
        setattr(namespace, self.dest, values)


def add_renamed_flag(
    parser: argparse.ArgumentParser,
    new: str,
    old: str,
    *,
    required: bool = False,
    help: str,
    metavar: str | None = None,
    dest: str | None = None,
    choices: Sequence[str] | None = None,
    default: Any = None,
) -> None:
    """`new` as the flag, plus `old` as a hidden deprecated alias (Issues
    #379, #380). Both store to one dest. They sit in a mutually exclusive
    group so a `required` flag is satisfied by either spelling."""
    dest = dest or new.lstrip("-").replace("-", "_")
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument(
        new, dest=dest, metavar=metavar, help=help, choices=choices, default=default
    )
    group.add_argument(
        old,
        dest=dest,
        metavar=metavar,
        choices=choices,
        action=_DeprecatedAlias,
        replacement=f"`{new}`",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )


def add_key_argument(parser: argparse.ArgumentParser, help: str, *, required: bool = True) -> None:
    """An item key given either as a positional `KEY` or as `--key KEY`
    (Issue #379: the docs and `slr sdb inspect` used the positional form,
    every other command `--key`). The flag stores to `key_flag`; call
    `resolve_key` to merge both into `args.key`."""
    parser.add_argument("key", nargs="?", metavar="KEY", help=help)
    parser.add_argument("--key", dest="key_flag", metavar="KEY", help=help)
    parser.set_defaults(_key_required=required)


def resolve_key(args: argparse.Namespace) -> None:
    """Merge `add_key_argument`'s two spellings into `args.key`."""
    from zotero_cli.core.exceptions import UsageError

    positional = getattr(args, "key", None)
    flag = getattr(args, "key_flag", None)
    positional = positional if isinstance(positional, str) else None
    flag = flag if isinstance(flag, str) else None
    if positional and flag and positional != flag:
        raise UsageError(f"Two different item keys given ({positional} and --key {flag}).")
    if positional or flag:
        args.key = flag or positional
    if getattr(args, "_key_required", False) is True and not args.key:
        raise UsageError("An item key is required: pass KEY or --key KEY.")


def add_format_flag(
    parser: argparse.ArgumentParser,
    choices: Sequence[str] = ("table", "json", "csv"),
    default: str = "table",
    help: str = "Output format: a table for people, json or csv for scripts (stdout carries only the data)",
) -> None:
    """`--format`, always meaning output rendering (Issue #380)."""
    parser.add_argument("--format", choices=list(choices), default=default, help=help)
