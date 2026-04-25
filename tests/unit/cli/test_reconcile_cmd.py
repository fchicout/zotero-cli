import argparse
from unittest.mock import MagicMock, patch
import pytest
from zotero_cli.cli.commands.slr.reconcile_cmd import ReconcileCommand
from zotero_cli.core.zotero_item import ZoteroItem

@pytest.fixture
def mock_deps():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mw, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service") as mc:
        yield mw.return_value, mc.return_value

def test_reconcile_command_dry_run(mock_deps):
    gateway, coll_service = mock_deps
    
    # Setup
    gateway.get_collection_id_by_name.return_value = "ROOT_KEY"
    gateway.get_collection.return_value = {"key": "ROOT_KEY", "data": {"name": "raw_test"}}
    
    # Mock papers in tree
    paper = ZoteroItem.from_raw_zotero_item({
        "key": "P1", "data": {"key": "P1", "version": 1, "collections": ["ROOT_KEY"], "itemType": "journalArticle", "title": "Test"}
    })
    
    with patch("zotero_cli.core.services.slr.orchestrator.SLROrchestrator.get_all_papers_in_tree") as gap, \
         patch("zotero_cli.core.services.slr.orchestrator.SLROrchestrator.get_tree_keys") as gtk, \
         patch("zotero_cli.core.services.slr.orchestrator.SLROrchestrator.resolve_target_phase") as rtp, \
         patch("zotero_cli.core.services.slr.orchestrator.SLROrchestrator.get_folder_key_for_phase") as gfk:
         
        gap.return_value = [paper]
        gtk.return_value = ["ROOT_KEY", "PHASE1_KEY"]
        rtp.return_value = "title_abstract"
        gfk.return_value = "PHASE1_KEY"
        
        args = argparse.Namespace(tree="raw_test", execute=False, verbose=False, user=False, qa_threshold=2.0)
        ReconcileCommand.execute(args)
        
        # Verify: Should NOT call move_item in dry run
        coll_service.move_item.assert_not_called()

def test_reconcile_command_execute(mock_deps):
    gateway, coll_service = mock_deps
    gateway.get_collection_id_by_name.return_value = "ROOT_KEY"
    gateway.get_collection.return_value = {"key": "ROOT_KEY", "data": {"name": "raw_test"}}
    
    paper = ZoteroItem.from_raw_zotero_item({
        "key": "P1", "data": {"key": "P1", "version": 1, "collections": ["ROOT_KEY"], "itemType": "journalArticle", "title": "Test"}
    })
    
    with patch("zotero_cli.core.services.slr.orchestrator.SLROrchestrator.get_all_papers_in_tree") as gap, \
         patch("zotero_cli.core.services.slr.orchestrator.SLROrchestrator.get_tree_keys") as gtk, \
         patch("zotero_cli.core.services.slr.orchestrator.SLROrchestrator.resolve_target_phase") as rtp, \
         patch("zotero_cli.core.services.slr.orchestrator.SLROrchestrator.get_folder_key_for_phase") as gfk:
         
        gap.return_value = [paper]
        gtk.return_value = ["ROOT_KEY", "PHASE1_KEY"]
        rtp.return_value = "title_abstract"
        gfk.return_value = "PHASE1_KEY"
        
        coll_service.move_item.return_value = True
        
        args = argparse.Namespace(tree="raw_test", execute=True, verbose=False, user=False, qa_threshold=2.0)
        ReconcileCommand.execute(args)
        
        # Verify: Should call move_item
        coll_service.move_item.assert_called_once()
