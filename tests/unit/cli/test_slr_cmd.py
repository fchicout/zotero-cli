import argparse
import json
from unittest.mock import Mock, patch

import pytest

from zotero_cli.cli.commands.slr_cmd import SLRCommand


@pytest.fixture
def slr_cmd():
    return SLRCommand()


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr_cmd.CollectionAuditor")
def test_slr_shift_dispatch(mock_auditor_cls, mock_gateway, slr_cmd, tmp_path):
    mock_auditor = mock_auditor_cls.return_value
    mock_auditor.detect_shifts.return_value = []

    snap1 = tmp_path / "snap1.json"
    snap1.write_text(json.dumps([]))
    snap2 = tmp_path / "snap2.json"
    snap2.write_text(json.dumps([]))

    args = argparse.Namespace(verb="shift", old=str(snap1), new=str(snap2), user=False)

    slr_cmd.execute(args)
    mock_auditor.detect_shifts.assert_called_once()


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr_cmd.MigrationService")
def test_slr_migrate_dispatch(mock_migrate_cls, mock_gateway, slr_cmd):
    mock_migrate = mock_migrate_cls.return_value
    mock_migrate.migrate_collection_notes.return_value = {
        "processed": 0,
        "migrated": 0,
        "failed": 0,
    }

    args = argparse.Namespace(verb="migrate", collection="C1", dry_run=True, user=False)

    slr_cmd.execute(args)
    mock_migrate.migrate_collection_notes.assert_called_once_with("C1", True)


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
@patch("zotero_cli.cli.commands.slr.verify_cmd.IntegrityService")
def test_slr_verify_collection_dispatch(mock_integrity_cls, mock_gateway, slr_cmd):
    mock_integrity = mock_integrity_cls.return_value
    mock_report = Mock()
    mock_report.items_missing_id = []
    mock_report.items_missing_title = []
    mock_report.items_missing_abstract = []
    mock_report.items_missing_pdf = []
    mock_report.items_missing_note = []
    mock_report.total_items = 0
    mock_integrity.audit_collection.return_value = mock_report

    args = argparse.Namespace(
        verb="verify",
        collection="Test",
        latex=None,
        verbose=False,
        user=False,
        export_missing=None,
    )

    slr_cmd.execute(args)
    mock_integrity.audit_collection.assert_called_once_with("Test")


@patch("zotero_cli.infra.factory.GatewayFactory.get_audit_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
def test_slr_verify_latex_dispatch(mock_gateway, mock_audit_service_get, slr_cmd):
    mock_service = mock_audit_service_get.return_value
    mock_service.audit_manuscript.return_value = {
        "path": "test.tex",
        "total_citations": 0,
        "items": {},
    }

    args = argparse.Namespace(
        verb="verify",
        latex="test.tex",
        collection=None,
        verbose=False,
        user=False,
        export_missing=None,
    )

    slr_cmd.execute(args)
    mock_service.audit_manuscript.assert_called_once()


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
@patch("zotero_cli.core.services.purge_service.PurgeService")
def test_slr_reset_dispatch(mock_purge_cls, mock_gateway_get, slr_cmd):
    mock_purge = mock_purge_cls.return_value
    mock_purge.purge_notes.return_value = {"deleted": 1, "skipped": 0, "errors": 0}
    mock_purge.purge_tags.return_value = {"deleted": 1, "skipped": 0, "errors": 0}

    mock_gateway = mock_gateway_get.return_value
    mock_item = Mock()
    mock_item.key = "K1"
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_items_in_collection.return_value = iter([mock_item])

    args = argparse.Namespace(
        verb="reset",
        name="MyCol",
        phase="title_abstract",
        persona="Pythias",
        force=True,
        user=False,
    )

    slr_cmd.execute(args)

    mock_purge.purge_notes.assert_called_once_with(
        ["K1"], sdb_only=True, phase="title_abstract", persona="Pythias", dry_run=False
    )
    mock_purge.purge_tags.assert_called_once_with(
        ["K1"], tag_name="rsl:phase:title_abstract", dry_run=False
    )
