"""
Coverage tests for:
  - src/zotero_cli/cli/commands/report_cmd.py (duplicates, stats, attachments)
"""

import argparse
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


class TestReportCommandDuplicates:
    def _make_dupe_item(self, key, title="Paper", doi="10.1/DUP"):
        raw_item = {
            "key": key,
            "data": {"version": 1, "itemType": "journalArticle", "title": title, "DOI": doi},
        }
        from zotero_cli.core.zotero_item import ZoteroItem

        return ZoteroItem.from_raw_zotero_item(raw_item)

    def test_duplicates_lists_both_copies_and_their_collections(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        item_a = self._make_dupe_item("KEY_A")
        item_b = self._make_dupe_item("KEY_B")
        mock_gateway.get_collection_id_by_name.side_effect = ["COL_A", "COL_B"]
        mock_gateway.get_items_in_collection.side_effect = [iter([item_a]), iter([item_b])]

        args = argparse.Namespace(
            report_type="duplicates", collections="Source,Target", csv=None, user=False
        )
        cmd = ReportCommand()
        with (
            patch(
                "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway",
                return_value=mock_gateway,
            ),
        ):
            cmd.execute(args)

        out = capsys.readouterr().out
        assert "KEY_A" in out
        assert "KEY_B" in out
        assert "SDB" not in out

    def test_duplicates_exports_csv(self, mock_gateway, capsys, tmp_path):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        item_a = self._make_dupe_item("KEY_A")
        item_b = self._make_dupe_item("KEY_B")
        mock_gateway.get_collection_id_by_name.side_effect = ["COL_A", "COL_B"]
        mock_gateway.get_items_in_collection.side_effect = [iter([item_a]), iter([item_b])]

        out_file = str(tmp_path / "dupes.csv")
        args = argparse.Namespace(
            report_type="duplicates", collections="Source,Target", csv=out_file, user=False
        )
        cmd = ReportCommand()
        with (
            patch(
                "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway",
                return_value=mock_gateway,
            ),
        ):
            cmd.execute(args)

        assert Path(out_file).exists()
        content = Path(out_file).read_text()
        assert content.splitlines()[0] == "match_type,identifier,key,title,collection"
        assert "KEY_A" in content
        assert "KEY_B" in content

    def test_duplicates_exports_csv_sanitizes_formula_injection(
        self, mock_gateway, capsys, tmp_path
    ):
        """Issue #237: a duplicate item's title (settable by any
        collaborator with write access to the library) must not reach
        the CSV as an evaluable spreadsheet formula."""
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        item_a = self._make_dupe_item("KEY_A", title='=HYPERLINK("http://attacker/","x")')
        item_b = self._make_dupe_item("KEY_B")
        mock_gateway.get_collection_id_by_name.side_effect = ["COL_A", "COL_B"]
        mock_gateway.get_items_in_collection.side_effect = [iter([item_a]), iter([item_b])]

        out_file = str(tmp_path / "dupes.csv")
        args = argparse.Namespace(
            report_type="duplicates", collections="Source,Target", csv=out_file, user=False
        )
        cmd = ReportCommand()
        with (
            patch(
                "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway",
                return_value=mock_gateway,
            ),
        ):
            cmd.execute(args)

        content = Path(out_file).read_text()
        assert "'=HYPERLINK" in content

    def test_duplicates_none_found(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        mock_gateway.get_collection_id_by_name.side_effect = ["COL_A", "COL_B"]
        mock_gateway.get_items_in_collection.side_effect = [iter([]), iter([])]

        args = argparse.Namespace(
            report_type="duplicates", collections="Source,Target", csv=None, user=False
        )
        cmd = ReportCommand()
        with patch(
            "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
        ):
            cmd.execute(args)

        assert "No duplicates found" in capsys.readouterr().out

    def test_duplicates_whole_library_scan_when_collections_omitted(self, mock_gateway, capsys):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        item_a = self._make_dupe_item("KEY_A")
        item_b = self._make_dupe_item("KEY_B")
        mock_gateway.get_all_items.return_value = iter([item_a, item_b])

        args = argparse.Namespace(report_type="duplicates", collections=None, csv=None, user=False)
        cmd = ReportCommand()
        with (
            patch(
                "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway",
                return_value=mock_gateway,
            ),
        ):
            cmd.execute(args)

        mock_gateway.get_all_items.assert_called_once()
        mock_gateway.get_items_in_collection.assert_not_called()
        out = capsys.readouterr().out
        assert "KEY_A" in out
        assert "KEY_B" in out

    def test_duplicates_export_plan_csv(self, mock_gateway, capsys, tmp_path):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        item_a = self._make_dupe_item("KEY_A")
        item_b = self._make_dupe_item("KEY_B")
        mock_gateway.get_collection_id_by_name.side_effect = ["COL_A", "COL_B"]
        mock_gateway.get_items_in_collection.side_effect = [iter([item_a]), iter([item_b])]

        out_file = str(tmp_path / "plan.csv")
        args = argparse.Namespace(
            report_type="duplicates",
            collections="Source,Target",
            csv=None,
            export_plan=out_file,
            user=False,
        )
        cmd = ReportCommand()
        with (
            patch(
                "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway",
                return_value=mock_gateway,
            ),
        ):
            cmd.execute(args)

        content = Path(out_file).read_text()
        assert "group_id" in content
        assert "role" in content
        assert "reason" in content
        assert "KEY_A" in content
        assert "KEY_B" in content
        assert "Exported a merge plan" in capsys.readouterr().out

    def test_duplicates_export_plan_json_is_a_plain_nested_plan(
        self, mock_gateway, capsys, tmp_path
    ):
        from zotero_cli.cli.commands.report_cmd import ReportCommand

        item_a = self._make_dupe_item("KEY_A")
        item_b = self._make_dupe_item("KEY_B")
        mock_gateway.get_collection_id_by_name.side_effect = ["COL_A", "COL_B"]
        mock_gateway.get_items_in_collection.side_effect = [iter([item_a]), iter([item_b])]

        out_file = str(tmp_path / "plan.json")
        args = argparse.Namespace(
            report_type="duplicates",
            collections="Source,Target",
            csv=None,
            export_plan=out_file,
            user=False,
        )
        cmd = ReportCommand()
        with (
            patch(
                "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway",
                return_value=mock_gateway,
            ),
        ):
            cmd.execute(args)

        content = Path(out_file).read_text()
        assert '"version"' in content
        assert "KEY_A" in content
        assert "sdb_history" not in content


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
