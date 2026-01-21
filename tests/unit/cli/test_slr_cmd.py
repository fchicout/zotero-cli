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


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr_cmd.CollectionAuditor")
def test_slr_validate_dispatch(mock_auditor_cls, mock_gateway, slr_cmd):
    mock_auditor = mock_auditor_cls.return_value
    mock_report = Mock()
    mock_report.items_missing_id = []
    mock_report.items_missing_title = []
    mock_report.items_missing_abstract = []
    mock_report.items_missing_pdf = []
    mock_report.items_missing_note = []
    mock_report.total_items = 0
    mock_auditor.audit_collection.return_value = mock_report

    args = argparse.Namespace(verb="validate", collection="C1", verbose=False, user=False)

    slr_cmd.execute(args)
    mock_auditor.audit_collection.assert_called_once_with("C1")


@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
@patch("zotero_cli.cli.commands.slr_cmd.CollectionAuditor")
def test_slr_load_dispatch(mock_auditor_cls, mock_gateway, slr_cmd):
    mock_auditor = mock_auditor_cls.return_value
    mock_auditor.enrich_from_csv.return_value = {
        "total_rows": 0,
        "matched": 0,
        "unmatched": [],
        "updated": 0,
        "created": 0,
        "skipped": 0,
    }

    args = argparse.Namespace(
        verb="load", file="test.csv", reviewer="Pythias", phase="full_text", force=True, user=False
    )

    slr_cmd.execute(args)
    mock_auditor.enrich_from_csv.assert_called_once_with(
        csv_path="test.csv", reviewer="Pythias", dry_run=False, force=True, phase="full_text"
    )
