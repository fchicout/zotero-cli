"""Issues #368/#370: main() turns failures into one stderr line and an exit
code that says what kind of failure it was; tracebacks only with -v."""

import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main
from zotero_cli.core import exceptions as exc
from zotero_cli.core.exceptions import OfflineReadOnly


def _run(error: BaseException, *flags: str):
    argv = ["zotero-cli", *flags, "system", "info"]
    with (
        patch.object(sys, "argv", argv),
        patch("zotero_cli.cli.commands.system_cmd.InfoCommand.execute", side_effect=error),
        pytest.raises(SystemExit) as raised,
    ):
        main()
    return raised.value.code


@pytest.mark.parametrize(
    "error, code",
    [
        (exc.ZoteroCliError("boom"), 1),
        (exc.ConfigurationError("no key"), 1),
        (OfflineReadOnly(), 1),
        (exc.UsageError("bad args"), 2),
        (exc.AmbiguousCollectionError("Inbox", [("A1", "Inbox"), ("B2", "X / Inbox")]), 2),
        (exc.NotFound("Item NOPE not found"), 3),
        (exc.AuthError("key rejected"), 4),
        (exc.Unavailable("network down"), 5),
        (exc.Conflict("changed since version 4"), 6),
        (exc.PartialFailure("2 of 5 failed"), 7),
        (exc.DataFileError("unreadable"), 1),
    ],
)
def test_typed_errors_map_to_exit_codes_without_a_traceback(capsys, error, code):
    assert _run(error) == code
    captured = capsys.readouterr()
    assert captured.err.startswith("Error: ")
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_error_prefix_is_not_doubled(capsys):
    _run(exc.ConfigurationError("Error: Zotero API Key not set."))
    assert capsys.readouterr().err.startswith("Error: Zotero API Key not set.")


def test_traceback_only_with_verbose(capsys):
    _run(exc.NotFound("gone"), "-v")
    assert "Traceback" in capsys.readouterr().err


def test_offline_read_only_is_the_shared_class():
    from zotero_cli.infra import sqlite_repo

    assert sqlite_repo.ConfigurationError is exc.ConfigurationError
    assert issubclass(OfflineReadOnly, exc.ConfigurationError)


def test_missing_file_is_one_line(capsys):
    assert _run(FileNotFoundError(2, "No such file or directory", "/nope.csv")) == 1
    err = capsys.readouterr().err
    assert err.strip() == "Error: No such file or directory: /nope.csv"


def test_prompt_without_a_terminal_is_a_usage_error(capsys):
    assert _run(EOFError()) == 2
    assert "--force" in capsys.readouterr().err


def test_ctrl_c_exits_130(capsys):
    assert _run(KeyboardInterrupt()) == 130
    assert "Traceback" not in capsys.readouterr().err


def test_unexpected_errors_point_to_verbose_and_the_log(capsys):
    assert _run(ValueError("weird")) == 1
    err = capsys.readouterr().err
    assert "Error: ValueError: weird" in err
    assert "Traceback" not in err
    assert "-v" in err


def test_offline_write_attempt_is_a_clean_error(capsys, tmp_path):
    """The reproduction from #370: an offline write printed a traceback."""
    import sqlite3

    db = tmp_path / "zotero.sqlite"
    sqlite3.connect(db).close()
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    with pytest.raises(OfflineReadOnly, match="without --offline"):
        SqliteZoteroGateway(str(db)).update_item("K", 1, {"title": "x"})
