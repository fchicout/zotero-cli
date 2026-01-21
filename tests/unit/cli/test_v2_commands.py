import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main
from zotero_cli.core.services.report_service import PrismaReport


@pytest.fixture
def mock_clients():
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_screening_service") as mock_screen_get,
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_zot_get,
    ):
        yield {"screening": mock_screen_get.return_value, "gateway": mock_zot_get.return_value}


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")


def test_decide_short_paper(mock_clients, env_vars, capsys):
    mock_clients["screening"].record_decision.return_value = True
    test_args = ["zotero-cli", "slr", "decide", "--key", "K1", "--short-paper", "EC5"]

    with patch.object(sys, "argv", test_args):
        main()

    mock_clients["screening"].record_decision.assert_called_once()
    call_kwargs = mock_clients["screening"].record_decision.call_args[1]
    assert call_kwargs["decision"] == "EXCLUDE"
    assert call_kwargs["code"] == "EC5"
    assert call_kwargs["reason"] == "Short Paper"


def test_decide_not_english(mock_clients, env_vars, capsys):
    mock_clients["screening"].record_decision.return_value = True
    test_args = ["zotero-cli", "slr", "decide", "--key", "K1", "--not-english", "EC2"]

    with patch.object(sys, "argv", test_args):
        main()

    call_kwargs = mock_clients["screening"].record_decision.call_args[1]
    assert call_kwargs["decision"] == "EXCLUDE"
    assert call_kwargs["code"] == "EC2"
    assert call_kwargs["reason"] == "Not English"


def test_decide_missing_args_error(mock_clients, env_vars, capsys):
    test_args = ["zotero-cli", "slr", "decide", "--key", "K1"]

    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit):
            main()

    assert "You must provide --vote and --code" in capsys.readouterr().out


def test_report_status_dashboard(mock_clients, env_vars, capsys):
    # Mock ReportService usage inside ReportCommand
    with patch("zotero_cli.cli.commands.report_cmd.ReportService") as mock_cls:
        mock_service = mock_cls.return_value
        report = PrismaReport(
            collection_name="TestCol",
            total_items=100,
            screened_items=50,
            accepted_items=10,
            rejected_items=40,
        )
        mock_service.generate_prisma_report.return_value = report

        test_args = ["zotero-cli", "report", "status", "--collection", "TestCol"]
        with patch.object(sys, "argv", test_args):
            main()

        out = capsys.readouterr().out
        assert "Status Report: TestCol" in out
        assert "50/100" in out  # Progress
        assert "Accepted" in out
        assert "Rejected" in out


def test_report_status_fallback_to_file(mock_clients, env_vars, capsys, tmp_path):
    with patch("zotero_cli.cli.commands.report_cmd.ReportService") as mock_cls:
        mock_service = mock_cls.return_value
        mock_service.generate_prisma_report.return_value = PrismaReport("TestCol")
        mock_service.generate_screening_markdown.return_value = "# MD Content"

        out_file = tmp_path / "dash.md"
        test_args = [
            "zotero-cli",
            "report",
            "status",
            "--collection",
            "TestCol",
            "--output",
            str(out_file),
        ]

        with patch.object(sys, "argv", test_args):
            main()

        assert "Screening report saved" in capsys.readouterr().out
        assert out_file.read_text() == "# MD Content"
