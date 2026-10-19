"""Shared argparse helpers for flags that more than one command defines."""

import argparse
from typing import Sequence


def add_details_flag(parser: argparse.ArgumentParser, help: str) -> None:
    """`--details` (Issue #374). The global `-v` is what turns on debug logging."""
    parser.add_argument("--details", action="store_true", help=help)


def add_key_argument(parser: argparse.ArgumentParser, help: str, *, required: bool = True) -> None:
    """An item key given either as a positional `KEY` or as `--key KEY`
    (Issue #379: the docs used the positional form, every
    other command `--key`). The flag stores to `key_flag`; call
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


def user_flag(args: argparse.Namespace) -> bool:
    """Whether the global `--user` flag asks for the personal library (Issue #383)."""
    return bool(getattr(args, "user", False))


# `--format` choices of the list-style commands: ndjson is one JSON object per line.
LIST_FORMATS = ("table", "json", "csv", "ndjson", "keys")
LIST_FORMAT_HELP = (
    "Output format: a table for people; json, csv, ndjson (one JSON object per line) or keys "
    "(one identifier per line) for scripts (stdout carries only the data)"
)


def add_format_flag(
    parser: argparse.ArgumentParser,
    choices: Sequence[str] = ("table", "json", "csv"),
    default: str = "table",
    help: str = "Output format: a table for people, json or csv for scripts (stdout carries only the data)",
) -> None:
    """`--format`, always meaning output rendering (Issue #380)."""
    parser.add_argument("--format", choices=list(choices), default=default, help=help)


def add_bibliography_flags(parser: argparse.ArgumentParser) -> None:
    """`--style` / `--render`, used with `--as bibliography` (Issue #534)."""
    parser.add_argument(
        "--style",
        default="apa",
        help="Citation style for --as bibliography: a CSL style id such as apa, ieee, "
        "chicago-author-date (default: apa)",
    )
    parser.add_argument(
        "--render",
        choices=["plain", "markdown", "html"],
        default="plain",
        help="How --as bibliography is rendered (default: plain)",
    )
