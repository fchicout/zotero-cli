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
        rejections_by_code={"EXC01": 3}
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
