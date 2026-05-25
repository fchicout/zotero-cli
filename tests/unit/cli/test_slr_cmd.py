import argparse
import json
from unittest.mock import Mock, patch

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
