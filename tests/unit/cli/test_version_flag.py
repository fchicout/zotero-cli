"""Issue #375: step 1 of the getting-started tutorial is `zotero-cli --version`."""

import sys
from unittest.mock import patch

import pytest

from zotero_cli import __version__
from zotero_cli.cli.main import main


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_version_flag_prints_the_version(flag, capsys):
    with patch.object(sys, "argv", ["zotero-cli", flag]), pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"zotero-cli {__version__}"


def test_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    assert tomllib.loads(pyproject.read_text())["project"]["version"] == __version__


def test_system_info_shows_version_python_and_platform(capsys):
    from zotero_cli.core.config import ZoteroConfig

    with (
        patch.object(sys, "argv", ["zotero-cli", "system", "info"]),
        patch("zotero_cli.core.config.get_config", return_value=ZoteroConfig()),
    ):
        main()

    out = capsys.readouterr().out
    assert f"Version:     {__version__}" in out
    assert "Python:" in out
    assert "Platform:" in out


@pytest.mark.parametrize("version", [(3, 11, 0), (3, 11, 4)])
def test_python_below_the_announced_floor_warns_on_stderr(version, capsys):
    """4.2.0 announces the 3.11.5 minimum that 4.3.0 enforces."""
    from zotero_cli.cli.main import warn_if_python_floor_ahead

    warn_if_python_floor_ahead(version)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "3.11.5" in captured.err
    assert f"{version[0]}.{version[1]}.{version[2]}" in captured.err


@pytest.mark.parametrize("version", [(3, 11, 5), (3, 11, 14), (3, 12, 0), (3, 14, 1)])
def test_python_at_or_above_the_floor_is_silent(version, capsys):
    from zotero_cli.cli.main import warn_if_python_floor_ahead

    warn_if_python_floor_ahead(version)

    assert capsys.readouterr() == ("", "")
