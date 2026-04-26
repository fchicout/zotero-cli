import argparse
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.slr.promote_cmd import PromoteCommand


@pytest.fixture
def mock_deps():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mg, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_slr_orchestrator") as mo, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_screening_service") as ms:
        yield mg.return_value, mo.return_value, ms.return_value

def test_promote_command_include(mock_deps, capsys):
    mock_gateway, mock_orchestrator, mock_screening = mock_deps
    mock_gateway.get_collection_id_by_name.return_value = "ROOT_KEY"
    mock_orchestrator.get_promotion_path.return_value = ("SRC_KEY", "DEST_KEY")
    mock_screening.record_decision.return_value = True

    args = argparse.Namespace(
        key="ITEM1", vote="INCLUDE", phase="full_text", tree="raw_acm",
        code=None, reason="Looks good", persona="Paula", user=False
    )

    PromoteCommand.execute(args)

    mock_screening.record_decision.assert_called_once_with(
        item_key="ITEM1", decision="INCLUDE", code="", reason="Looks good",
        source_collection="SRC_KEY", target_collection="DEST_KEY",
        persona="Paula", phase="full_text"
    )
    out = capsys.readouterr().out
    assert "Success" in out

def test_promote_command_exclude(mock_deps, capsys):
    mock_gateway, mock_orchestrator, mock_screening = mock_deps
    mock_gateway.get_collection_id_by_name.return_value = "ROOT_KEY"
    mock_orchestrator.get_promotion_path.return_value = ("SRC_KEY", "DEST_KEY")
    mock_screening.record_decision.return_value = True

    args = argparse.Namespace(
        key="ITEM1", vote="EXCLUDE", phase="title_abstract", tree="raw_acm",
        code="EC1", reason="Out of scope", persona="Paula", user=False
    )

    PromoteCommand.execute(args)

    # EXCLUDE should NOT set move_target
    mock_screening.record_decision.assert_called_once_with(
        item_key="ITEM1", decision="EXCLUDE", code="EC1", reason="Out of scope",
        source_collection=None, target_collection=None,
        persona="Paula", phase="title_abstract"
    )

def test_promote_command_no_path(mock_deps, capsys):
    mock_gateway, mock_orchestrator, mock_screening = mock_deps
    mock_orchestrator.get_promotion_path.return_value = (None, None)

    args = argparse.Namespace(
        key="ITEM1", vote="INCLUDE", phase="unknown", tree="raw_acm",
        code=None, reason=None, persona="P", user=False
    )

    PromoteCommand.execute(args)
    out = capsys.readouterr().out
    assert "Error: Could not resolve folders" in out
