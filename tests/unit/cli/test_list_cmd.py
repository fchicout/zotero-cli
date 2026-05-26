import argparse
import sys
from unittest.mock import MagicMock, mock_open, patch

try:
    import openpyxl  # noqa: F401
except ImportError:
    sys.modules["openpyxl"] = MagicMock()

try:
    import odf  # noqa: F401
except ImportError:
    sys.modules["odf"] = MagicMock()
    sys.modules["odf.opendocument"] = MagicMock()
    sys.modules["odf.table"] = MagicMock()
    sys.modules["odf.text"] = MagicMock()

import pytest

from zotero_cli.cli.commands.slr.list_cmd import ListCommand


@pytest.fixture
def mock_slr_status_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_slr_status_service") as mock_factory:
        service = MagicMock()
        mock_factory.return_value = service
        yield service


def test_register_args():
    parser = argparse.ArgumentParser()
    ListCommand.register_args(parser)

    # Test pending parsing
    args = parser.parse_args(["pending", "--tree", "raw_acm"])
    assert args.list_verb == "pending"
    assert args.tree == "raw_acm"

    # Test included parsing
    args = parser.parse_args(["included", "--tree", "raw_ieee", "--ta"])
    assert args.list_verb == "included"
    assert args.tree == "raw_ieee"
    assert args.ta is True
    assert args.fullscreen is False
    assert args.qa is None


def test_handle_pending_empty(mock_slr_status_service, capsys):
    mock_slr_status_service.get_pending_items.return_value = []

    args = argparse.Namespace(
        list_verb="pending",
        tree="raw_acm",
        user=False
    )

    ListCommand.execute(args)
    mock_slr_status_service.get_pending_items.assert_called_once_with(root_key="raw_acm")
    out = capsys.readouterr().out
    assert "No pending papers found!" in out


def test_handle_pending_success(mock_slr_status_service, capsys):
    item1 = MagicMock()
    item1.item_key = "K1"
    item1.phase = "01_title_abstract"
    item1.source_collection = "raw_acm"
    item1.reason = "Awaiting decision"
    item1.title = "Short Title"

    item2 = MagicMock()
    item2.item_key = "K2"
    item2.phase = "02_full_text"
    item2.source_collection = "raw_acm"
    item2.reason = "Awaiting PDF download"
    item2.title = "A very long title that exceeds eighty characters in length to test the truncation logic in the CLI presenter"

    mock_slr_status_service.get_pending_items.return_value = [item1, item2]

    args = argparse.Namespace(
        list_verb="pending",
        tree="raw_acm",
        user=False
    )

    ListCommand.execute(args)

    out = capsys.readouterr().out
    assert "Pending SLR Items" in out
    assert "K1" in out
    assert "Short Title" in out
    assert "K2" in out
    assert "..." in out  # check truncation


def test_handle_decided_included_empty(mock_slr_status_service, capsys):
    mock_slr_status_service.get_decided_items.return_value = []

    args = argparse.Namespace(
        list_verb="included",
        tree="raw_acm",
        ta=True,
        fullscreen=False,
        qa=None,
        user=False
    )

    ListCommand.execute(args)
    mock_slr_status_service.get_decided_items.assert_called_once_with(
        "accepted", root_key="raw_acm", phase_filter="title_abstract"
    )
    out = capsys.readouterr().out
    assert "No accepted papers found for the specified filters" in out


def test_handle_decided_excluded_success(mock_slr_status_service, capsys):
    item = MagicMock()
    item.item_key = "K3"
    item.phase = "full_text"
    item.source_collection = "raw_acm"
    item.reason = "EX1"
    item.title = "Rejected Paper"

    mock_slr_status_service.get_decided_items.return_value = [item]

    args = argparse.Namespace(
        list_verb="excluded",
        tree="raw_acm",
        ta=False,
        fullscreen=True,
        qa=None,
        user=False
    )

    ListCommand.execute(args)
    mock_slr_status_service.get_decided_items.assert_called_once_with(
        "rejected", root_key="raw_acm", phase_filter="full_text"
    )
    out = capsys.readouterr().out
    assert "Rejected SLR Items" in out
    assert "K3" in out
    assert "EX1" in out


def test_handle_decided_qa_filter(mock_slr_status_service, capsys):
    mock_slr_status_service.get_decided_items.return_value = []

    args = argparse.Namespace(
        list_verb="included",
        tree="raw_acm",
        ta=False,
        fullscreen=False,
        qa=2.0,
        user=False
    )

    ListCommand.execute(args)
    mock_slr_status_service.get_decided_items.assert_called_once_with(
        "accepted", root_key="raw_acm", phase_filter="quality_assessment"
    )


def test_handle_qa_approved_empty(mock_slr_status_service, capsys):
    mock_slr_status_service.get_decided_items.return_value = []

    args = argparse.Namespace(
        list_verb="qa-approved",
        tree="raw_acm",
        csv=None,
        json=None,
        xlsx=None,
        ods=None,
        user=False
    )

    ListCommand.execute(args)
    mock_slr_status_service.get_decided_items.assert_called_once_with(
        "accepted", root_key="raw_acm", phase_filter="quality_assessment"
    )
    out = capsys.readouterr().out
    assert "No QA-approved papers found" in out


@patch("builtins.open", new_callable=mock_open)
def test_handle_qa_approved_csv_json_export(mock_file, mock_slr_status_service, capsys):
    item = MagicMock()
    item.item_key = "K1"
    item.title = "QA Paper"
    item.source_collection = "raw_acm"
    item.reason = "3.5"

    mock_slr_status_service.get_decided_items.return_value = [item]

    args = argparse.Namespace(
        list_verb="qa-approved",
        tree="raw_acm",
        csv="out.csv",
        json="out.json",
        xlsx=None,
        ods=None,
        user=False
    )

    ListCommand.execute(args)

    out = capsys.readouterr().out
    assert "Successfully exported to CSV: out.csv" in out
    assert "Successfully exported to JSON: out.json" in out


def test_handle_qa_approved_xlsx_export(mock_slr_status_service, capsys):
    item = MagicMock()
    item.item_key = "K1"
    item.title = "QA Paper"
    item.source_collection = "raw_acm"
    item.reason = "3.5"

    mock_slr_status_service.get_decided_items.return_value = [item]

    args = argparse.Namespace(
        list_verb="qa-approved",
        tree="raw_acm",
        csv=None,
        json=None,
        xlsx="out.xlsx",
        ods=None,
        user=False
    )

    mock_wb = MagicMock()
    with patch("openpyxl.Workbook", return_value=mock_wb):
        ListCommand.execute(args)

    out = capsys.readouterr().out
    assert "Successfully exported to XLSX: out.xlsx" in out


def test_handle_qa_approved_ods_export(mock_slr_status_service, capsys):
    item = MagicMock()
    item.item_key = "K1"
    item.title = "QA Paper"
    item.source_collection = "raw_acm"
    item.reason = "3.5"

    mock_slr_status_service.get_decided_items.return_value = [item]

    args = argparse.Namespace(
        list_verb="qa-approved",
        tree="raw_acm",
        csv=None,
        json=None,
        xlsx=None,
        ods="out.ods",
        user=False
    )

    mock_doc = MagicMock()
    with (
        patch("odf.opendocument.OpenDocumentSpreadsheet", return_value=mock_doc),
        patch("odf.table.Table"),
        patch("odf.table.TableRow"),
        patch("odf.table.TableCell"),
        patch("odf.text.P")
    ):
        ListCommand.execute(args)

    out = capsys.readouterr().out
    assert "Successfully exported to ODS: out.ods" in out


def test_handle_qa_approved_import_errors(mock_slr_status_service, capsys):
    item = MagicMock()
    item.item_key = "K1"
    item.title = "QA Paper"
    item.source_collection = "raw_acm"
    item.reason = "3.5"

    mock_slr_status_service.get_decided_items.return_value = [item]

    args = argparse.Namespace(
        list_verb="qa-approved",
        tree="raw_acm",
        csv=None,
        json=None,
        xlsx="out.xlsx",
        ods="out.ods",
        user=False
    )

    with (
        patch("openpyxl.Workbook", side_effect=ImportError),
        patch("odf.opendocument.OpenDocumentSpreadsheet", side_effect=ImportError)
    ):
        ListCommand.execute(args)

    out = capsys.readouterr().out
    assert "Workbook" not in out
    assert "Cannot export to XLSX" in out
    assert "Cannot export to ODS" in out


def test_handle_qa_approved_console_table(mock_slr_status_service, capsys):
    item = MagicMock()
    item.item_key = "K1"
    item.title = "QA Paper Title that is moderately long but not super long"
    item.source_collection = "raw_acm"
    item.reason = "3.5"

    mock_slr_status_service.get_decided_items.return_value = [item]

    args = argparse.Namespace(
        list_verb="qa-approved",
        tree="raw_acm",
        csv=None,
        json=None,
        xlsx=None,
        ods=None,
        user=False
    )

    ListCommand.execute(args)

    out = capsys.readouterr().out
    assert "QA-Approved SLR Items" in out
    assert "K1" in out
    assert "raw_acm" in out
    assert "3.5" in out
    assert "QA Paper Title" in out

