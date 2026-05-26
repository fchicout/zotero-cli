import argparse
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.slr_cmd import SLRCommand


@pytest.fixture
def slr_cmd():
    return SLRCommand()


@patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
def test_slr_prune_dispatch(mock_gateway, mock_coll_service_get, slr_cmd):
    mock_service = mock_coll_service_get.return_value
    mock_service.prune_intersection.return_value = 0

    args = argparse.Namespace(verb="prune", included="INC", excluded="EXC", user=False)

    slr_cmd.execute(args)
    mock_service.prune_intersection.assert_called_once_with("INC", "EXC")


@patch("zotero_cli.infra.factory.GatewayFactory.get_screening_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
def test_slr_decide_dispatch_full(mock_gateway, mock_screening_get, slr_cmd):
    mock_service = mock_screening_get.return_value
    mock_service.record_decision.return_value = True

    args = argparse.Namespace(
        verb="decide",
        key="K1",
        vote="INCLUDE",
        code="IC1",
        reason="Good",
        source="S",
        target="T",
        agent_led=True,
        persona="Pythias",
        phase="full_text",
        evidence="Evidence text",
        short_paper=None,
        not_english=None,
        is_survey=None,
        no_pdf=None,
        user=False,
    )

    slr_cmd.execute(args)
    mock_service.record_decision.assert_called_once_with(
        item_key="K1",
        decision="INCLUDE",
        code="IC1",
        reason="Good",
        source_collection="S",
        target_collection="T",
        agent="zotero-cli",
        persona="Pythias",
        phase="full_text",
        evidence="Evidence text",
    )


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.LoadCommand.execute")
def test_slr_load_dispatch(mock_load_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(
        verb="load",
        file="test.csv",
        reviewer="Pythias",
        phase="full_text",
        force=True,
        user=False,
        move_to_included="INC",
        move_to_excluded="EXC",
    )

    slr_cmd.execute(args)
    mock_load_execute.assert_called_once_with(mock_gateway.return_value, args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.report_cmd.SLRReportCommand.execute")
def test_slr_report_dispatch(mock_report_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(
        verb="report",
        report_verb="status",
        collection="C1",
        user=False
    )
    slr_cmd.execute(args)
    mock_report_execute.assert_called_once_with(mock_gateway.return_value, args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.source_cmd.SLRSourceCommand.execute")
def test_slr_source_dispatch(mock_source_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(
        verb="source",
        source_verb="init",
        name="acm",
        user=False
    )
    slr_cmd.execute(args)
    mock_source_execute.assert_called_once_with(mock_gateway.return_value, args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.screen_cmd.ScreenCommand.execute")
def test_slr_screen_dispatch(mock_screen_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(verb="screen", file=None, user=False)
    slr_cmd.execute(args)
    mock_screen_execute.assert_called_once_with(args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.list_cmd.ListCommand.execute")
def test_slr_list_dispatch(mock_list_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(verb="list", user=False)
    slr_cmd.execute(args)
    mock_list_execute.assert_called_once_with(args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.reconcile_cmd.ReconcileCommand.execute")
def test_slr_reconcile_dispatch(mock_reconcile_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(verb="reconcile", user=False)
    slr_cmd.execute(args)
    mock_reconcile_execute.assert_called_once_with(args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.promote_cmd.PromoteCommand.execute")
def test_slr_promote_dispatch(mock_promote_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(verb="promote", user=False)
    slr_cmd.execute(args)
    mock_promote_execute.assert_called_once_with(args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.extraction_cmd.ExtractionCommand.execute")
def test_slr_extraction_dispatch(mock_extract_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(verb="extract", user=False)
    slr_cmd.execute(args)
    mock_extract_execute.assert_called_once_with(args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.sdb_cmd.SDBCommand.execute")
def test_slr_sdb_dispatch(mock_sdb_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(verb="sdb", user=False)
    slr_cmd.execute(args)
    mock_sdb_execute.assert_called_once_with(mock_gateway.return_value, args)


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr.snowball_cmd.SnowballCommand.execute")
def test_slr_snowball_dispatch(mock_snowball_execute, mock_gateway, slr_cmd):
    args = argparse.Namespace(verb="snowball", user=False)
    slr_cmd.execute(args)
    mock_snowball_execute.assert_called_once_with(mock_gateway.return_value, args)


@patch("builtins.open")
@patch("zotero_cli.infra.factory.GatewayFactory.get_screening_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
def test_slr_bulk_decide_success(mock_gateway, mock_screening_get, mock_open_file, slr_cmd, capsys):
    mock_service = mock_screening_get.return_value
    mock_service.record_decision.return_value = True

    # mock csv reader
    mock_open_file.return_value.__enter__.return_value = ["Key,Vote,Reason\n", "K1,INCLUDE,Good\n"]
    with patch("csv.DictReader") as mock_dict_reader:
        mock_dict_reader.return_value = [{"Key": "K1", "Vote": "INCLUDE", "Reason": "Good"}]

        args = argparse.Namespace(verb="screen", file="decisions.csv", user=False)
        slr_cmd.execute(args)

    out = capsys.readouterr().out
    assert "Done. Success: 1" in out


@patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
def test_slr_prune_no_intersection(mock_gateway, mock_coll_service_get, slr_cmd, capsys):
    mock_service = mock_coll_service_get.return_value
    mock_service.prune_intersection.return_value = 0

    args = argparse.Namespace(verb="prune", included="INC", excluded="EXC", user=False)
    slr_cmd.execute(args)

    out = capsys.readouterr().out
    assert "No intersection found" in out


def test_slr_register_args(slr_cmd):
    parser = argparse.ArgumentParser()
    slr_cmd.register_args(parser)
    actions = parser._actions
    assert len(actions) > 0


@patch("builtins.open", side_effect=Exception("Read error"))
@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
def test_slr_bulk_decide_exception(mock_gateway, mock_open_file, slr_cmd, capsys):
    args = argparse.Namespace(verb="screen", file="decisions.csv", user=False)
    slr_cmd.execute(args)

    out = capsys.readouterr().out
    assert "Error processing CSV: Read error" in out


