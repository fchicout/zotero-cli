"""Issue #363: `--offline` was lost when main.py ran as `__main__` (the
PyInstaller binaries run the script; `python -m` runs the module), because
the flag was read back through a second import of zotero_cli.cli.main."""

import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import zotero_cli.cli.main as cli_main
from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.runtime import is_offline_mode, set_offline_mode


@pytest.fixture(autouse=True)
def _reset_offline_mode():
    set_offline_mode(False)
    yield
    set_offline_mode(False)


def _run_as_main(runner, capsys) -> str:
    """Runs `--offline tag list` with a config that has no database_path:
    offline mode stops with a database_path error, online mode with an
    API-key error, so the message shows which gateway was chosen."""
    config = ZoteroConfig(api_key=None, database_path=None)
    with (
        patch.object(sys, "argv", ["zotero-cli", "--offline", "tag", "list"]),
        patch("zotero_cli.core.config.get_config", return_value=config),
        pytest.raises(SystemExit),
    ):
        runner()
    captured = capsys.readouterr()
    return str(captured.out + captured.err)


def test_offline_survives_running_main_py_as_a_script(capsys):
    """What the PyInstaller binaries (Linux, Windows, Docker) do."""
    script = Path(cli_main.__file__)
    output = _run_as_main(lambda: runpy.run_path(str(script), run_name="__main__"), capsys)

    assert "database_path" in output
    assert "API Key" not in output
    assert is_offline_mode()


# runpy warns that zotero_cli.cli.main is already imported; that is the point.
@pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")
def test_offline_survives_python_dash_m(capsys):
    output = _run_as_main(
        lambda: runpy.run_module("zotero_cli.cli.main", run_name="__main__"), capsys
    )

    assert "database_path" in output
    assert is_offline_mode()


def test_main_resets_offline_mode_when_the_flag_is_absent():
    set_offline_mode(True)
    with (
        patch.object(sys, "argv", ["zotero-cli", "--version"]),
        pytest.raises(SystemExit),
    ):
        cli_main.main()
    # --version exits during parsing; a parsed run without --offline sets it back.
    with (
        patch.object(sys, "argv", ["zotero-cli", "tag", "list"]),
        patch("zotero_cli.core.config.get_config", return_value=ZoteroConfig()),
        pytest.raises(SystemExit),
    ):
        cli_main.main()
    assert not is_offline_mode()
