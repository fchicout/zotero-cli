"""Issue #513: a console whose codepage can't encode our status glyphs
(Windows cp1252) used to crash the command with UnicodeEncodeError."""

import io
import sys

import pytest

from zotero_cli.core.utils.terminal_safety import SafeConsole, make_output_streams_tolerant


def _stream(encoding: str, errors: str = "strict"):
    raw = io.BytesIO()
    return raw, io.TextIOWrapper(raw, encoding=encoding, errors=errors, write_through=True)


def _glyph_line(console_stream) -> None:
    console = SafeConsole(file=console_stream, force_terminal=False, width=80)
    console.print("[bold green]✓ Created parent collection[/bold green]")
    console.print("[bold green]✅ ARCHIVE IS VALID[/bold green]")


def test_a_strict_cp1252_stream_really_crashes_without_the_fix():
    """Guards the premise: if this stops raising, the fix has nothing to fix."""
    _, stream = _stream("cp1252")
    with pytest.raises(UnicodeEncodeError):
        _glyph_line(stream)


def test_a_cp1252_console_prints_question_marks_instead_of_crashing(monkeypatch):
    raw, stream = _stream("cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    make_output_streams_tolerant()
    _glyph_line(sys.stdout)

    assert raw.getvalue().decode("cp1252").count("?") == 2
    assert b"Created parent collection" in raw.getvalue()


def test_stderr_is_made_tolerant_too(monkeypatch):
    raw, stream = _stream("cp1252")
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", stream)

    make_output_streams_tolerant()
    print("⚠ warning", file=sys.stderr)

    assert raw.getvalue().decode("cp1252").startswith("? warning")


def test_a_utf8_console_still_shows_the_real_glyphs(monkeypatch):
    raw, stream = _stream("utf-8")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    make_output_streams_tolerant()
    _glyph_line(sys.stdout)

    assert "✓" in raw.getvalue().decode("utf-8")
    assert "✅" in raw.getvalue().decode("utf-8")


def test_the_encoding_itself_is_never_changed(monkeypatch):
    _, stream = _stream("cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    make_output_streams_tolerant()

    assert sys.stdout.encoding == "cp1252"
    assert sys.stdout.errors == "replace"


def test_streams_that_cannot_be_reconfigured_are_left_alone(monkeypatch):
    class Plain:
        """A stdout replaced by a pager or a test: no reconfigure()."""

        errors = "strict"

    plain = Plain()
    monkeypatch.setattr(sys, "stdout", plain)
    monkeypatch.setattr(sys, "stderr", plain)

    make_output_streams_tolerant()

    assert plain.errors == "strict"


def test_an_already_tolerant_stream_is_not_touched(monkeypatch):
    _, stream = _stream("cp1252", errors="backslashreplace")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    make_output_streams_tolerant()

    assert sys.stdout.errors == "backslashreplace"


def test_main_makes_the_streams_tolerant_before_parsing(monkeypatch, capsys):
    from zotero_cli.cli import main as cli_main

    calls = []
    monkeypatch.setattr(cli_main, "make_output_streams_tolerant", lambda: calls.append("tolerant"))
    monkeypatch.setattr(sys, "argv", ["zotero-cli", "--version"])
    with pytest.raises(SystemExit):
        cli_main.main()

    assert calls == ["tolerant"]
