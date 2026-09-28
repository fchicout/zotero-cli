"""Issue #367: `slr report status` and a preview `slr reconcile` created the
four phase folders under any collection they looked at (and crashed in
offline mode, which is read-only)."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.services.slr.orchestrator import SLROrchestrator
from zotero_cli.core.zotero_item import ZoteroItem

ROOT = {"key": "ROOT", "data": {"name": "My Reading List", "parentCollection": False}}
PHASE1 = {"key": "PH1", "data": {"name": "1-title_abstract", "parentCollection": "ROOT"}}


def _read_only_gateway(collections):
    gateway = MagicMock()
    gateway.get_all_collections.return_value = collections
    gateway.get_items_in_collection.return_value = []
    gateway.create_collection.side_effect = AssertionError("a read-only path created a collection")
    return gateway


def test_find_returns_only_existing_phase_folders():
    orchestrator = SLROrchestrator(_read_only_gateway([ROOT, PHASE1]))

    assert orchestrator.find_slr_hierarchy("ROOT") == {"1-title_abstract": "PH1"}
    assert orchestrator.get_tree_keys("ROOT") == ["ROOT", "PH1"]


def test_reading_a_tree_never_creates_folders():
    orchestrator = SLROrchestrator(_read_only_gateway([ROOT]))

    assert orchestrator.get_all_papers_in_tree("ROOT") == []
    assert orchestrator.get_tree_keys("ROOT") == ["ROOT"]


def test_ensure_still_creates_missing_folders_for_write_paths():
    gateway = _read_only_gateway([ROOT, PHASE1])
    gateway.create_collection.side_effect = lambda name, parent_key: f"NEW-{name}"

    phase_map = SLROrchestrator(gateway).ensure_slr_hierarchy("ROOT")

    assert phase_map["1-title_abstract"] == "PH1"
    assert gateway.create_collection.call_count == 3


def test_status_report_creates_nothing():
    from zotero_cli.core.services.slr.status_service import SLRStatusService

    gateway = _read_only_gateway([ROOT])
    service = SLRStatusService(gateway, SLROrchestrator(gateway))

    service.get_slr_status("My Reading List")
    service.get_pending_items("ROOT")
    service.get_decided_items("accepted", "ROOT")

    gateway.create_collection.assert_not_called()


def _paper():
    return ZoteroItem.from_raw_zotero_item(
        {"key": "P1", "data": {"key": "P1", "version": 1, "collections": ["ROOT"],
                               "itemType": "journalArticle", "title": "Paper"}}
    )


@pytest.fixture
def reconcile_env():
    gateway = _read_only_gateway([ROOT])
    gateway.get_collection_id_by_name.return_value = "ROOT"
    gateway.get_collection.return_value = ROOT
    gateway.get_items_in_collection.return_value = [_paper()]
    gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "note": '{"sdb_version": "1.2", '
                               '"phase": "title_abstract", "decision": "accepted"}'}}
    ]
    coll_service = MagicMock()
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway),
        patch("zotero_cli.infra.factory.GatewayFactory.get_slr_orchestrator",
              return_value=SLROrchestrator(gateway)),
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service",
              return_value=coll_service),
    ):
        yield gateway, coll_service


def test_reconcile_preview_plans_a_missing_folder_without_creating_it(reconcile_env, capsys):
    from zotero_cli.cli.commands.slr.reconcile_cmd import ReconcileCommand

    gateway, coll_service = reconcile_env
    ReconcileCommand.execute(
        argparse.Namespace(tree="ROOT", execute=False, verbose=False, user=False, qa_threshold=2.0)
    )

    gateway.create_collection.assert_not_called()
    coll_service.move_item.assert_not_called()
    assert "created with --execute" in " ".join(capsys.readouterr().out.split())


def test_reconcile_execute_creates_the_folder_then_moves(reconcile_env):
    from zotero_cli.cli.commands.slr.reconcile_cmd import ReconcileCommand

    gateway, coll_service = reconcile_env
    gateway.create_collection.side_effect = lambda name, parent_key: f"NEW-{name}"
    coll_service.move_item.return_value = True

    ReconcileCommand.execute(
        argparse.Namespace(tree="ROOT", execute=True, verbose=False, user=False, qa_threshold=2.0)
    )

    assert gateway.create_collection.called
    coll_service.move_item.assert_called_once_with("ROOT", "NEW-1-title_abstract", "P1")
