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
    from pathlib import Path

    import tomllib

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
