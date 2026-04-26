import argparse
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.report_cmd import ReportCommand
from zotero_cli.cli.commands.slr.decide_cmd import DecideCommand
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
    args = argparse.Namespace(
        verb="decide",
        key="K1",
        short_paper="EC5",
        not_english=None,
        is_survey=None,
        no_pdf=None,
        vote="EXCLUDE",
        code="EC5",
        reason="Short Paper",
        persona="human",
        phase="title_abstract",
        agent_led=False,
        source=None,
        target=None,
        evidence=None,
    )

    # We call DecideCommand.execute directly
    DecideCommand.execute(args)

    mock_clients["screening"].record_decision.assert_called_once()
    call_kwargs = mock_clients["screening"].record_decision.call_args[1]
    assert call_kwargs["decision"] == "EXCLUDE"
    assert call_kwargs["code"] == "EC5"
    assert call_kwargs["reason"] == "Short Paper"


def test_decide_not_english(mock_clients, env_vars, capsys):
    mock_clients["screening"].record_decision.return_value = True
    args = argparse.Namespace(
        verb="decide",
        key="K1",
        short_paper=None,
        not_english="EC2",
        is_survey=None,
        no_pdf=None,
        vote="EXCLUDE",
        code="EC2",
        reason="Not English",
        persona="human",
        phase="title_abstract",
        agent_led=False,
        source=None,
        target=None,
        evidence=None,
    )

    DecideCommand.execute(args)

    call_kwargs = mock_clients["screening"].record_decision.call_args[1]
    assert call_kwargs["decision"] == "EXCLUDE"
    assert call_kwargs["code"] == "EC2"
    assert call_kwargs["reason"] == "Not English"


def test_report_status_dashboard(mock_clients, env_vars, capsys):
    # Mock ReportService usage inside ReportCommand
    with patch("zotero_cli.cli.commands.report_cmd.ReportService") as mock_cls:
        mock_service = mock_cls.value = mock_cls.return_value
        report = PrismaReport(
            collection_name="TestCol",
            total_items=100,
            screened_items=50,
            accepted_items=10,
            rejected_items=40,
        )
        mock_service.generate_prisma_report.return_value = report

        args = argparse.Namespace(
            report_type="status", collection="TestCol", output=None, user=False
        )
        ReportCommand().execute(args)

        out = capsys.readouterr().out
        assert "Status Report: TestCol" in out
        assert "50/100" in out  # Progress


def test_report_status_fallback_to_file(mock_clients, env_vars, capsys, tmp_path):
    with patch("zotero_cli.cli.commands.report_cmd.ReportService") as mock_cls:
        mock_service = mock_cls.return_value
        mock_service.generate_prisma_report.return_value = PrismaReport("TestCol")
        mock_service.generate_screening_markdown.return_value = "# MD Content"

        out_file = tmp_path / "dash.md"
        args = argparse.Namespace(
            report_type="status", collection="TestCol", output=str(out_file), user=False
        )

        ReportCommand().execute(args)

        assert "Screening report saved" in capsys.readouterr().out
        assert out_file.read_text() == "# MD Content"
