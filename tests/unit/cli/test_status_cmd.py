import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand
from zotero_cli.core.services.report_service import PrismaReport


@pytest.fixture
def mock_deps():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mw:
        yield mw.return_value


def test_status_command_execute(mock_deps, capsys):
    # Setup
    mock_report = PrismaReport(
        collection_name="raw_test",
        total_items=15,
        screened_items=5,
        accepted_items=2,
        rejected_items=3,
        rejections_by_code={"EXC01": 3},
    )

    with patch(
        "zotero_cli.core.services.report_service.ReportService.generate_prisma_report",
        return_value=mock_report,
    ):
        args = argparse.Namespace(verb="report", report_verb="status", collection="raw_test")
        SLRReportCommand.execute(MagicMock(), args)

        out = capsys.readouterr().out
        assert "SLR Funnel Status" in out
        assert "raw_test" in out
        assert "15" in out  # Total
        assert "Accepted (Included)" in out
        assert "Rejected (Excluded)" in out


def test_status_command_grid_view(mock_deps, capsys):
    from zotero_cli.core.services.slr.status_service import PhaseStats, SLRStatus

    mock_status = SLRStatus(
        source_name="raw_test",
        source_key="ABCDEF12",
        tree_total=10,
        phases={
            "title_abstract": PhaseStats(accepted=5, rejected=3, pending=2),
            "full_text": PhaseStats(
                accepted=2, rejected=1, pending=0
            ),  # pen=0 triggers ✔ checkmark
            "quality_assessment": PhaseStats(
                accepted=1, rejected=0, pending=0
            ),  # pen=0 triggers ✔ checkmark
            "data_extraction": PhaseStats(accepted=1, rejected=0, pending=0),
        },
    )

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_slr_status_service"
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_slr_status.return_value = [mock_status]
        mock_get_service.return_value = mock_service

        args = argparse.Namespace(verb="report", report_verb="status", all_sources=True)
        SLRReportCommand.execute(MagicMock(), args)

        out = capsys.readouterr().out
        assert "SLR Progress Status" in out
        assert "raw_test" in out
        assert "ABCDEF12" in out
        assert "10" in out
        assert "5/3/2" in out
        assert "2/1/0" in out
        assert "✔" in out
        assert "TOTAL" in out
        assert "SUM" in out
