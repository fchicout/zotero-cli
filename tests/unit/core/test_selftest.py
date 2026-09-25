"""Issue #403: `system selftest` proves the install can convert a PDF, not
only that it imports; the release workflow runs it on every binary."""

import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main
from zotero_cli.core.services import selftest


def test_selftest_passes_on_this_install():
    results = selftest.run_selftest()

    assert [r.name for r in results] == ["PDF text extraction", "SQLite (offline mode)"]
    assert all(r.ok for r in results), results


def test_selftest_reports_a_broken_pdf_backend():
    with patch(
        "zotero_cli.core.services.attachment_service.extract_pdf_text",
        side_effect=ModuleNotFoundError("No module named 'pdfminer'"),
    ):
        result = selftest._check_pdf_extraction()

    assert not result.ok
    assert "pdfminer" in result.detail


def test_system_selftest_exits_1_when_a_check_fails(capsys):
    failing = [selftest.SelfTestResult("PDF text extraction", False, "boom")]
    with (
        patch.object(sys, "argv", ["zotero-cli", "system", "selftest"]),
        patch("zotero_cli.core.services.selftest.run_selftest", return_value=failing),
        pytest.raises(SystemExit) as exc,
    ):
        main()

    assert exc.value.code == 1
    assert "FAILED" in capsys.readouterr().out


def test_system_selftest_exits_0_when_all_pass(capsys):
    with patch.object(sys, "argv", ["zotero-cli", "system", "selftest"]):
        main()

    assert "FAILED" not in capsys.readouterr().out
