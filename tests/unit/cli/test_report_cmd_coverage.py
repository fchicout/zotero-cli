"""
Coverage tests for:
  - src/zotero_cli/cli/commands/report_cmd.py (stats, attachments, verify-latex)
  - src/zotero_cli/cli/commands/slr/report_cmd.py (prisma, shift, snapshot, screening,
    exclusion-summary, consensus)
"""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_gateway():
    gw = MagicMock()
    gw.get_collection_id_by_name.return_value = "COL_KEY"
    return gw


def _make_item(key="KEY1", title="Paper", item_type="journalArticle"):
    item = MagicMock()
    item.key = key
    item.title = title
    item.item_type = item_type
    item.raw_data = {"data": {"date": "2023", "creators": [{"name": "Author A"}]}}
    return item


# ===========================================================================
# report_cmd.py — ReportCommand handlers
# ===========================================================================


class TestReportCommandStats:
    def test_stats_full_library(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        items = [_make_item("K1"), _make_item("K2")]
        mock_gateway.get_all_items.return_value = items

        args = argparse.Namespace(report_type="stats", collection=None, user=False)
        cmd = ReportCommand()
        with patch(
            "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
        ):
            cmd.execute(args)

        out = capsys.readouterr().out
        assert "Library Global Metrics" in out
        assert "Total Items" in out

    def test_stats_specific_collection(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        items = [_make_item("K1")]
        mock_gateway.get_items_in_collection.return_value = items

        args = argparse.Namespace(report_type="stats", collection="TestCol", user=False)
        cmd = ReportCommand()
        with patch(
            "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
        ):
            cmd.execute(args)

        out = capsys.readouterr().out
        assert "Library Global Metrics" in out

    def test_stats_empty_library(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        mock_gateway.get_all_items.return_value = []
        args = argparse.Namespace(report_type="stats", collection=None, user=False)
        cmd = ReportCommand()
        with patch(
            "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
        ):
            cmd.execute(args)

        out = capsys.readouterr().out
        assert "No items found" in out


class TestReportCommandAttachments:
    def _make_attach_item(self, key, content_type="application/pdf", filesize=1024):
        item = MagicMock()
        item.key = key
        item.item_type = "attachment"
        item.title = f"File {key}"
        item.raw_data = {"data": {"contentType": content_type, "filesize": filesize}}
        return item

    def test_attachments_full_library(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        items = [self._make_attach_item("A1"), self._make_attach_item("A2", "text/html", 512)]
        mock_gateway.get_all_items.return_value = items

        args = argparse.Namespace(
            report_type="attachments", collection=None, output=None, user=False
        )
        cmd = ReportCommand()
        with patch(
            "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
        ):
            cmd.execute(args)

        out = capsys.readouterr().out
        assert "Attachments and Disk Usage Audit" in out
        assert "Total Attachments" in out

    def test_attachments_with_collection_missing_pdf(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        article = _make_item("J1", "Article without PDF", "journalArticle")
        mock_gateway.get_items_in_collection.return_value = [article]
        mock_gateway.get_item_children.return_value = []  # no children = no PDF

        args = argparse.Namespace(
            report_type="attachments", collection="TestCol", output=None, user=False
        )
        cmd = ReportCommand()
        with patch(
            "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
        ):
            cmd.execute(args)

        out = capsys.readouterr().out
        assert "Items Missing PDF" in out

    def test_attachments_exports_markdown(self, mock_gateway, capsys, tmp_path):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        mock_gateway.get_all_items.return_value = []
        out_file = str(tmp_path / "report.md")

        args = argparse.Namespace(
            report_type="attachments", collection=None, output=out_file, user=False
        )
        cmd = ReportCommand()
        with patch(
            "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
        ):
            cmd.execute(args)

        assert Path(out_file).exists()


class TestReportCommandVerifyLatex:
    def test_verify_latex_all_ok(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        mock_report = {
            "total_citations": 2,
            "items": {
                "K1": {
                    "exists": True,
                    "screened": True,
                    "decision": "accepted",
                    "title": "Paper A",
                },
                "K2": {
                    "exists": True,
                    "screened": True,
                    "decision": "included",
                    "title": "Paper B",
                },
            },
        }

        args = argparse.Namespace(report_type="verify-latex", latex="manuscript.tex", user=False)
        cmd = ReportCommand()
        with patch("zotero_cli.infra.factory.GatewayFactory.get_audit_service") as mock_svc_get:
            mock_svc_get.return_value.audit_manuscript.return_value = mock_report
            cmd.execute(args)

        out = capsys.readouterr().out
        assert "Verification Success" in out

    def test_verify_latex_with_missing(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        mock_report = {
            "total_citations": 1,
            "items": {
                "MISSING1": {"exists": False, "screened": False, "decision": None, "title": ""},
            },
        }

        args = argparse.Namespace(report_type="verify-latex", latex="manuscript.tex", user=False)
        cmd = ReportCommand()
        with patch("zotero_cli.infra.factory.GatewayFactory.get_audit_service") as mock_svc_get:
            mock_svc_get.return_value.audit_manuscript.return_value = mock_report
            with pytest.raises(SystemExit):
                cmd.execute(args)

        out = capsys.readouterr().out
        assert "Verification Failed" in out

    def test_verify_latex_no_citations(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        mock_report = {"total_citations": 0, "items": {}}

        args = argparse.Namespace(report_type="verify-latex", latex="empty.tex", user=False)
        cmd = ReportCommand()
        with patch("zotero_cli.infra.factory.GatewayFactory.get_audit_service") as mock_svc_get:
            mock_svc_get.return_value.audit_manuscript.return_value = mock_report
            cmd.execute(args)

        out = capsys.readouterr().out
        assert "No citations found" in out


# ===========================================================================
# slr/report_cmd.py — SLRReportCommand handlers
# ===========================================================================


@pytest.fixture
def mock_prisma_report():
    from zotero_cli.core.services.report_service import PrismaReport

    return PrismaReport(
        collection_name="TestCol",
        total_items=50,
        screened_items=40,
        accepted_items=15,
        rejected_items=25,
        rejections_by_code={"EXC01": 10, "EXC02": 15},
    )


class TestSLRReportCommandPrisma:
    def test_prisma_success(self, mock_gateway, mock_prisma_report, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        args = argparse.Namespace(
            report_verb="prisma", collection="TestCol", output_chart=None, verbose=False
        )
        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            mock_svc_cls.return_value.generate_prisma_report.return_value = mock_prisma_report
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "PRISMA Screening Summary" in out
        assert "TestCol" in out
        assert "Rejection Reasons" in out

    def test_prisma_not_found_exits(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        args = argparse.Namespace(
            report_verb="prisma", collection="NoExist", output_chart=None, verbose=False
        )
        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            mock_svc_cls.return_value.generate_prisma_report.return_value = None
            with pytest.raises(SystemExit):
                SLRReportCommand.execute(mock_gateway, args)

    def test_prisma_with_chart_success(self, mock_gateway, mock_prisma_report, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        args = argparse.Namespace(
            report_verb="prisma", collection="TestCol", output_chart="/tmp/chart.png", verbose=False
        )
        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            svc = mock_svc_cls.return_value
            svc.generate_prisma_report.return_value = mock_prisma_report
            svc.generate_mermaid_prisma.return_value = "graph TD;"
            svc.render_diagram.return_value = True
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "Flowchart saved" in out

    def test_prisma_with_chart_failure(self, mock_gateway, mock_prisma_report, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        args = argparse.Namespace(
            report_verb="prisma", collection="TestCol", output_chart="/tmp/chart.png", verbose=False
        )
        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            svc = mock_svc_cls.return_value
            svc.generate_prisma_report.return_value = mock_prisma_report
            svc.generate_mermaid_prisma.return_value = "graph TD;"
            svc.render_diagram.return_value = False
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "Failed to render" in out


class TestSLRReportCommandShift:
    def test_shift_no_shifts(self, mock_gateway, tmp_path, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        old_snap = tmp_path / "old.json"
        new_snap = tmp_path / "new.json"
        old_snap.write_text(json.dumps({"items": []}))
        new_snap.write_text(json.dumps({"items": []}))

        args = argparse.Namespace(report_verb="shift", old=str(old_snap), new=str(new_snap))
        with patch("zotero_cli.cli.commands.slr.report_cmd.CollectionAuditor") as mock_aud:
            mock_aud.return_value.detect_shifts.return_value = []
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "No shifts detected" in out

    def test_shift_with_shifts(self, mock_gateway, tmp_path, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        old_snap = tmp_path / "old.json"
        new_snap = tmp_path / "new.json"
        old_snap.write_text(json.dumps([]))
        new_snap.write_text(json.dumps([]))

        shifts = [
            {"key": "K1", "title": "Paper A", "from": ["raw_ieee"], "to": ["1-title_abstract"]}
        ]
        args = argparse.Namespace(report_verb="shift", old=str(old_snap), new=str(new_snap))
        with patch("zotero_cli.cli.commands.slr.report_cmd.CollectionAuditor") as mock_aud:
            mock_aud.return_value.detect_shifts.return_value = shifts
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "K1" in out


class TestSLRReportCommandSnapshot:
    def test_snapshot_success(self, mock_gateway, tmp_path, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        out_file = str(tmp_path / "snap.json")
        args = argparse.Namespace(report_verb="snapshot", collection="TestCol", output=out_file)
        with patch("zotero_cli.cli.commands.slr.report_cmd.SnapshotService") as mock_svc:
            mock_svc.return_value.freeze_collection.return_value = True
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "Snapshot saved" in out

    def test_snapshot_failure_exits(self, mock_gateway, tmp_path, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        out_file = str(tmp_path / "snap.json")
        args = argparse.Namespace(report_verb="snapshot", collection="TestCol", output=out_file)
        with patch("zotero_cli.cli.commands.slr.report_cmd.SnapshotService") as mock_svc:
            mock_svc.return_value.freeze_collection.return_value = False
            with pytest.raises(SystemExit):
                SLRReportCommand.execute(mock_gateway, args)


class TestSLRReportCommandScreening:
    def test_screening_success(self, mock_gateway, tmp_path, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand
        from zotero_cli.core.services.report_service import PrismaReport

        report = PrismaReport("TestCol", 10, 8, 3, 5)
        out_file = str(tmp_path / "screen.md")
        args = argparse.Namespace(report_verb="screening", collection="TestCol", output=out_file)

        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            svc = mock_svc_cls.return_value
            svc.generate_prisma_report.return_value = report
            svc.generate_screening_markdown.return_value = "# Screening Report\n"
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "Screening report saved" in out
        assert Path(out_file).exists()

    def test_screening_not_found_exits(self, mock_gateway, tmp_path, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        out_file = str(tmp_path / "screen.md")
        args = argparse.Namespace(report_verb="screening", collection="NoExist", output=out_file)

        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            mock_svc_cls.return_value.generate_prisma_report.return_value = None
            with pytest.raises(SystemExit):
                SLRReportCommand.execute(mock_gateway, args)


class TestSLRReportCommandExclusionSummary:
    def test_exclusion_summary_success(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand
        from zotero_cli.core.services.report_service import PrismaReport

        report = PrismaReport("TestCol", 20, 15, 5, 10, rejections_by_code={"EXC01": 6, "EXC02": 4})
        args = argparse.Namespace(report_verb="exclusion-summary", collection="TestCol")

        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            mock_svc_cls.return_value.generate_prisma_report.return_value = report
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "Exclusion Summary Report" in out
        assert "EXC01" in out

    def test_exclusion_summary_no_codes(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand
        from zotero_cli.core.services.report_service import PrismaReport

        report = PrismaReport("TestCol", 10, 10, 5, 5, rejections_by_code={})
        args = argparse.Namespace(report_verb="exclusion-summary", collection="TestCol")

        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            mock_svc_cls.return_value.generate_prisma_report.return_value = report
            SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "No exclusion decisions found" in out

    def test_exclusion_summary_not_found_exits(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        args = argparse.Namespace(report_verb="exclusion-summary", collection="NoExist")

        with patch("zotero_cli.cli.commands.slr.report_cmd.ReportService") as mock_svc_cls:
            mock_svc_cls.return_value.generate_prisma_report.return_value = None
            with pytest.raises(SystemExit):
                SLRReportCommand.execute(mock_gateway, args)


class TestSLRReportCommandConsensus:
    def _make_item_with_notes(self, key, notes_data):
        """Create a gateway item with structured SDB notes."""
        item = MagicMock()
        item.key = key
        item.title = f"Paper {key}"
        item.item_type = "journalArticle"

        children = []
        for nd in notes_data:
            children.append({"data": {"itemType": "note", "note": json.dumps(nd)}})
        return item, children

    def test_consensus_no_discrepancies(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        item = MagicMock()
        item.key = "K1"
        item.title = "Paper K1"
        # Two reviewers agree
        children = [
            {
                "data": {
                    "itemType": "note",
                    "note": json.dumps({"decision": "accepted", "reviewer": "Alice"}),
                }
            },
            {
                "data": {
                    "itemType": "note",
                    "note": json.dumps({"decision": "accepted", "reviewer": "Bob"}),
                }
            },
        ]
        mock_gateway.get_items_in_collection.return_value = [item]
        mock_gateway.get_item_children.return_value = children

        args = argparse.Namespace(report_verb="consensus", collection="TestCol")
        SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "Perfect consensus" in out

    def test_consensus_with_conflict(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        item = MagicMock()
        item.key = "K1"
        item.title = "Paper K1"
        # Two reviewers disagree
        children = [
            {
                "data": {
                    "itemType": "note",
                    "note": json.dumps({"decision": "accepted", "reviewer": "Alice"}),
                }
            },
            {
                "data": {
                    "itemType": "note",
                    "note": json.dumps({"decision": "rejected", "reviewer": "Bob"}),
                }
            },
        ]
        mock_gateway.get_items_in_collection.return_value = [item]
        mock_gateway.get_item_children.return_value = children

        args = argparse.Namespace(report_verb="consensus", collection="TestCol")
        SLRReportCommand.execute(mock_gateway, args)

        out = capsys.readouterr().out
        assert "Discrepanc" in out

    def test_consensus_collection_not_found_exits(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

        mock_gateway.get_collection_id_by_name.return_value = None
        # simulate collection key lookup failing too
        mock_gateway.get_items_in_collection.return_value = []

        args = argparse.Namespace(report_verb="consensus", collection="NoExist")
        # Should not crash, just show empty consensus
        SLRReportCommand.execute(mock_gateway, args)
        out = capsys.readouterr().out
        assert "Perfect consensus" in out  # empty = no conflicts
