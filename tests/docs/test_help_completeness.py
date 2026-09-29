"""Issue #387: every leaf command's `--help` has a worked example, and every
option has help text. README.md tells an agent it can run `--help` on any
command "since each one includes worked examples" - 42 of 93 leaf commands
had none, and 22 options had no help text at all.

`test_examples_parse.py` already extracts and checks every `zotero-cli ...`
example found anywhere, including in epilogs; this only checks presence
(does each leaf have at least one?), not whether it parses.
"""

import argparse
from typing import Iterator, Tuple

import pytest

from zotero_cli.cli.main import build_parser


def _leaves(parser: argparse.ArgumentParser, path: str = "") -> Iterator[Tuple[str, argparse.ArgumentParser]]:
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subparsers:
        yield path, parser
        return
    seen = set()
    for name, sub in subparsers[0].choices.items():
        if id(sub) in seen:  # aliases
            continue
        seen.add(id(sub))
        yield from _leaves(sub, f"{path} {name}".strip())


def _commands_without_an_example() -> list:
    missing = []
    for path, parser in _leaves(build_parser()):
        if not path:
            continue
        if "zotero-cli " not in (parser.epilog or ""):
            missing.append(path)
    return missing


def _options_without_help() -> list:
    missing = []
    for path, parser in _leaves(build_parser()):
        if not path:
            continue
        for action in parser._actions:
            if isinstance(action, (argparse._SubParsersAction, argparse._HelpAction)):
                continue
            if not action.help:
                opt = "/".join(action.option_strings) if action.option_strings else action.dest
                missing.append(f"{path} {opt}")
    return missing


@pytest.mark.docs
def test_every_leaf_command_has_a_worked_example():
    missing = _commands_without_an_example()
    assert not missing, (
        f"{len(missing)} leaf command(s) have no `zotero-cli ...` example in their --help "
        f"epilog: {missing}"
    )


@pytest.mark.docs
def test_every_option_has_help_text():
    missing = _options_without_help()
    assert not missing, f"{len(missing)} option(s) have no help text: {missing}"
