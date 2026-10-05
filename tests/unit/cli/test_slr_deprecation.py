"""Issue #541: the slr commands (and report verify-latex) are deprecated for 4.0.0."""

import argparse
import sys

import pytest

import zotero_cli.cli.main as cli_main
from zotero_cli.cli.deprecation import (
    DEPRECATED_COMMANDS,
    is_deprecated,
    warn_deprecated_command,
)
from zotero_cli.cli.schema import build_schema, leaf_paths


def _leaves():
    return [tuple(p.split()) for p in leaf_paths(cli_main.build_parser())]


def test_every_slr_leaf_and_verify_latex_is_deprecated_and_nothing_else_is():
    deprecated = {p for p in _leaves() if is_deprecated(p)}

    assert deprecated
    assert all(p[0] == "slr" or p == ("report", "verify-latex") for p in deprecated)
    assert len([p for p in deprecated if p[0] == "slr"]) == 34
    assert ("report", "verify-latex") in deprecated
    assert not any(is_deprecated(p) for p in _leaves() if p[0] not in {"slr", "report"})
    assert not is_deprecated(("report", "stats"))
    assert not is_deprecated(("item", "merge"))


def test_the_schema_marks_exactly_the_deprecated_commands():
    schema = build_schema(cli_main.build_parser())
    seen: dict = {}

    def walk(node):
        seen[tuple(node["path"])] = node["deprecated"]
        for child in node.get("commands", []):
            walk(child)

    for command in schema["commands"]:
        walk(command)

    assert seen[("slr",)]["removed_in"] == "4.0.0"
    assert seen[("slr", "report", "prisma")] is not None
    assert seen[("report", "verify-latex")] is not None
    assert seen[("report", "stats")] is None
    assert seen[("item", "list")] is None
    assert {p for p, v in seen.items() if v} == {p for p in seen if is_deprecated(p)}


@pytest.mark.parametrize(
    "args, warns",
    [
        (argparse.Namespace(command="slr", verb="screen"), True),
        (argparse.Namespace(command="report", report_type="verify-latex"), True),
        (argparse.Namespace(command="report", report_type="stats"), False),
        (argparse.Namespace(command="item", verb="list"), False),
    ],
)
def test_the_warning_goes_to_stderr_only_for_deprecated_commands(capsys, args, warns):
    warn_deprecated_command(args)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert ("deprecated and will be removed in 4.0.0" in captured.err) is warns


def test_a_run_prints_the_warning_once_before_the_command(monkeypatch, capsys):
    from zotero_cli.cli.commands.slr_cmd import SLRCommand

    calls = []
    monkeypatch.setattr(SLRCommand, "execute", lambda self, args: calls.append("ran"))
    monkeypatch.setattr(cli_main, "get_config", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["zotero-cli", "slr", "list", "pending"])

    cli_main.main()

    captured = capsys.readouterr()
    assert calls == ["ran"]
    assert captured.err.count("deprecated and will be removed in 4.0.0") == 1
    assert "`zotero-cli slr`" in captured.err
    assert captured.out == ""


def test_the_deprecated_list_is_small_and_explicit():
    assert DEPRECATED_COMMANDS == (("slr",), ("report", "verify-latex"))
