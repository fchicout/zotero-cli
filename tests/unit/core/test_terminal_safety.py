"""Untrusted text must not reach the terminal as escape sequences or be
parsed as Rich markup."""

import ast
import io
from pathlib import Path

import pytest
from rich.table import Table
from rich.text import Text

import zotero_cli
from zotero_cli.cli.presenters import item_list_presenter as presenter
from zotero_cli.core.utils.terminal_safety import SafeConsole, safe_markup, strip_controls
from zotero_cli.core.zotero_item import ZoteroItem

OSC52_CLIPBOARD = "\x1b]52;c;ZWNobyBwd25lZA==\x07"
OSC8_LINK = "\x1b]8;;https://evil.example\x1b\\click me\x1b]8;;\x1b\\"
CSI_CLEAR = "\x1b[2J"
C1_CSI = "\x9b31m"
BIDI_OVERRIDE = "\u202egnp.exe"


def _console():
    return SafeConsole(file=io.StringIO(), width=200, force_terminal=True, color_system="standard")


@pytest.mark.parametrize("payload", [OSC52_CLIPBOARD, OSC8_LINK, CSI_CLEAR, C1_CSI, BIDI_OVERRIDE])
def test_strip_controls_removes_escape_sequences_introducers(payload):
    cleaned = strip_controls(f"Title {payload} end")
    for ch in ("\x1b", "\x07", "\x9b", "\u202e"):
        assert ch not in cleaned


def test_strip_controls_keeps_newlines_tabs_and_unicode():
    text = "Título\tçã\nnext — ok"
    assert strip_controls(text) == text


def test_safe_console_strips_escapes_from_text_but_keeps_rich_styling():
    console = _console()
    console.print(Text(f"A {OSC52_CLIPBOARD}paper", style="bold red"))
    out = console.file.getvalue()
    assert "\x1b]52" not in out and "\x07" not in out  # inert without ESC/BEL
    assert "A " in out and "paper" in out
    assert "\x1b[1" in out  # Rich's own styling (bold) survives


def test_item_list_table_does_not_emit_osc52_from_a_title():
    """The #253 path: titles in the default item list table."""
    console = _console()
    item = ZoteroItem.from_raw_zotero_item(
        {"key": "K1", "data": {"itemType": "journalArticle", "title": f"Paper{OSC52_CLIPBOARD}"}}
    )
    presenter.render_table([item], ["key", "title"], "Items", console)
    out = console.file.getvalue()
    assert "\x1b]52" not in out and "\x07" not in out
    assert "Paper" in out


def _plain_console():
    return SafeConsole(file=io.StringIO(), width=200, color_system=None)


def test_safe_markup_neutralises_markup_in_data():
    console = _plain_console()
    console.print(f"[bold]Title:[/bold] {safe_markup('[/bold] [link=https://evil.example]x')}")
    out = console.file.getvalue()
    assert "[/bold]" in out and "[link=https://evil.example]" in out
    assert "\x1b]8;" not in out  # no hyperlink emitted


def test_safe_markup_blocks_hyperlink_markup_on_a_terminal():
    console = _console()
    console.print(f"Title: {safe_markup('[link=https://evil.example]x[/link]')}")
    assert "\x1b]8;" not in console.file.getvalue()


def test_table_cell_with_safe_markup_renders_literally():
    console = _plain_console()
    table = Table()
    table.add_column("Title")
    table.add_row(safe_markup("[red]not red[/red]"))
    console.print(table)
    assert "[red]not red[/red]" in console.file.getvalue()


def test_no_module_uses_rich_console_directly():
    """Every console must be a SafeConsole."""
    src = Path(next(iter(zotero_cli.__path__)))
    allowed = {"core/utils/terminal_safety.py", "cli/main.py"}  # main: Python-version pre-flight
    offenders = []
    for path in src.rglob("*.py"):
        rel = path.relative_to(src).as_posix()
        if rel in allowed:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "rich.console":
                if any(alias.name == "Console" for alias in node.names):
                    offenders.append(rel)
    assert not offenders, f"Use terminal_safety.SafeConsole instead: {offenders}"
