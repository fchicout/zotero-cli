"""Issues #372 and #401: stdout carries data only (so `--format json|csv`
can be piped), diagnostics go to stderr, and Rich markup is never printed
through the builtin print()."""

import ast
import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "zotero_cli"
MARKUP = re.compile(r"\[/?(bold|red|yellow|green|cyan|dim|italic)?[^\]\n]*\]")


def _prints(paths):
    for path in paths:
        src = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print":
                yield path, node, ast.get_source_segment(src, node) or ""


def test_domain_code_never_prints_to_stdout():
    domain = [p for sub in ("core", "infra", "api") for p in (SRC / sub).rglob("*.py")]
    offenders = [
        f"{path.relative_to(SRC)}:{node.lineno}"
        for path, node, _ in _prints(domain)
        if not any(k.arg == "file" for k in node.keywords)
    ]
    assert not offenders, f"print() to stdout in domain code (use stderr or a logger): {offenders}"


def test_rich_markup_is_never_passed_to_builtin_print():
    offenders = [
        f"{path.relative_to(SRC)}:{node.lineno}"
        for path, node, text in _prints(SRC.rglob("*.py"))
        if re.search(r"\[/(bold|red|yellow|green|cyan|dim|italic)?\]|\[/\]", text)
    ]
    assert not offenders, f"Rich markup through builtin print() shows up literally: {offenders}"


@pytest.mark.skipif(
    os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
def test_json_output_stays_valid_with_an_unreadable_config(tmp_path, capsys):
    """The #372 reproduction: a config-load warning went to stdout and
    corrupted `--format json`."""
    from zotero_cli.cli.main import main
    from zotero_cli.core.config import reset_config
    from zotero_cli.core.zotero_item import ZoteroItem

    config = tmp_path / "config.toml"
    config.write_text("[zotero]\n")
    config.chmod(0)
    item = ZoteroItem.from_raw_zotero_item(
        {"key": "K1", "data": {"itemType": "book", "title": "T", "collections": ["C1"]}}
    )
    gateway = MagicMock()
    gateway.get_collection_id_by_name.return_value = "C1"
    gateway.get_items_in_collection.return_value = iter([item])
    argv = [
        "zotero-cli",
        "--config",
        str(config),
        "item",
        "list",
        "--collection",
        "C1",
        "--format",
        "json",
    ]
    try:
        with (
            patch.object(sys, "argv", argv),
            patch(
                "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway
            ),
        ):
            main()
    finally:
        config.chmod(0o600)
        reset_config()

    captured = capsys.readouterr()
    assert json.loads(captured.out)[0]["key"] == "K1"
    assert "Failed to load config file" in captured.err
