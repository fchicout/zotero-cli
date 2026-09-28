"""Subcommand options must not overwrite the global ones (Issue #374)."""

import argparse

import pytest

from zotero_cli.cli.main import build_parser

GLOBAL_DESTS = {"verbose", "user", "offline", "config"}


def _leaves(parser, path=()):
    subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subs:
        yield path, parser
        return
    seen = set()
    for name, sub in subs[0].choices.items():
        if id(sub) in seen:  # aliases
            continue
        seen.add(id(sub))
        yield from _leaves(sub, path + (name,))


def test_no_subcommand_reuses_a_global_dest():
    root = build_parser()
    clashes = []
    for path, leaf in _leaves(root):
        if not path:
            continue
        for action in leaf._actions:
            if action.dest in GLOBAL_DESTS:
                clashes.append(f"{' '.join(path)}: {'/'.join(action.option_strings)}")
        clashes += [f"{' '.join(path)}: default {k}" for k in leaf._defaults if k in GLOBAL_DESTS]
    assert not clashes, "a subcommand default would reset a global flag: " + ", ".join(clashes)


@pytest.mark.parametrize(
    "argv",
    [
        ["-v", "import", "file", "x.bib", "--collection", "C"],
        ["-v", "item", "pdf", "fetch", "--key", "K"],
        ["-v", "collection", "clean", "--collection", "C"],
        ["-v", "item", "list", "--root"],
    ],
)
def test_global_verbose_survives_the_subcommand(argv):
    args = build_parser().parse_args(argv)
    assert args.verbose is True


def test_subcommand_verbose_sets_details_not_debug_logging():
    args = build_parser().parse_args(["import", "file", "x.bib", "--collection", "C", "--verbose"])
    assert args.details is True
    assert args.verbose is False
