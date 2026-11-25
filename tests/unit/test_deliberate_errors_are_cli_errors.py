"""The exceptions raised on purpose (refused URL, oversized response or archive, failed PDF
resolution) are expected failures: one line and an exit code, not an unexpected crash
(Issue #709, from #611)."""

import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main
from zotero_cli.core.exceptions import ZoteroCliError
from zotero_cli.core.interfaces import ResolutionError
from zotero_cli.core.utils.archive_safety import ArchiveLimitError
from zotero_cli.core.utils.url_safety import ResponseTooLargeError, UnsafeURLError


@pytest.mark.parametrize(
    "error", [UnsafeURLError, ResponseTooLargeError, ArchiveLimitError, ResolutionError]
)
def test_the_error_is_an_expected_cli_failure(error: type) -> None:
    assert issubclass(error, ZoteroCliError)
    assert error.exit_code == 1  # type: ignore[attr-defined]


@pytest.mark.parametrize("error", [UnsafeURLError, ResponseTooLargeError, ArchiveLimitError])
def test_the_value_errors_are_still_value_errors(error: type) -> None:
    """Handlers written as `except ValueError` keep catching them."""
    assert issubclass(error, ValueError)


def test_an_uncaught_one_is_one_line_and_exit_1(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch.object(sys, "argv", ["zotero-cli", "system", "info"]),
        patch("zotero_cli.cli.main.get_config", side_effect=UnsafeURLError("blocked: 10.0.0.1")),
    ):
        with pytest.raises(SystemExit) as raised:
            main()

    assert raised.value.code == 1
    err = capsys.readouterr().err
    assert "blocked: 10.0.0.1" in err
    assert "Traceback" not in err
