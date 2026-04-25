import pytest
from unittest.mock import MagicMock
from zotero_cli.core.services.slr.orchestrator import SLROrchestrator

@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def orchestrator(mock_gateway):
    return SLROrchestrator(mock_gateway)

def test_ensure_slr_hierarchy_existing(orchestrator, mock_gateway):
    parent_key = "ROOT"
    all_cols = [
        {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "ROOT"}},
        {"key": "C2", "data": {"name": "2-fulltext", "parentCollection": "ROOT"}},
        {"key": "C3", "data": {"name": "3-quality_assessment", "parentCollection": "ROOT"}},
        {"key": "C4", "data": {"name": "4-data_extraction", "parentCollection": "ROOT"}},
    ]
    
    phase_map = orchestrator.ensure_slr_hierarchy(parent_key, all_cols)
    
    assert len(phase_map) == 4
    assert phase_map["1-title_abstract"] == "C1"
    assert phase_map["4-data_extraction"] == "C4"
    mock_gateway.create_collection.assert_not_called()

def test_ensure_slr_hierarchy_missing(orchestrator, mock_gateway):
    parent_key = "ROOT"
    all_cols = []
    mock_gateway.create_collection.side_effect = ["NEW1", "NEW2", "NEW3", "NEW4"]
    
    phase_map = orchestrator.ensure_slr_hierarchy(parent_key, all_cols)
    
    assert len(phase_map) == 4
    assert phase_map["1-title_abstract"] == "NEW1"
    assert mock_gateway.create_collection.call_count == 4

def test_resolve_target_phase_sequential(orchestrator, mock_gateway):
    item_key = "ITEM"
    # Notes for T&A and FT with SDB markers
    note_ta = {"data": {"itemType": "note", "note": '{"phase": "title_abstract", "decision": "accepted", "audit_version": "1.2"}'}}
    note_ft = {"data": {"itemType": "note", "note": '{"phase": "full_text", "decision": "accepted", "audit_version": "1.2"}'}}
    note_qa = {"data": {"itemType": "note", "note": '{"phase": "quality_assessment", "quality_assessment": {"total": 1.0}, "audit_version": "1.2"}'}} # Failed QA (default 2.0)
    
    mock_gateway.get_item_children.return_value = [note_ta, note_ft, note_qa]
    
    phase = orchestrator.resolve_target_phase(item_key, default_qa_threshold=2.0)
    assert phase == "full_text"

def test_resolve_target_phase_qa_success(orchestrator, mock_gateway):
    item_key = "ITEM"
    note_ta = {"data": {"itemType": "note", "note": '{"phase": "title_abstract", "decision": "accepted", "audit_version": "1.2"}'}}
    note_ft = {"data": {"itemType": "note", "note": '{"phase": "full_text", "decision": "accepted", "audit_version": "1.2"}'}}
    note_qa = {"data": {"itemType": "note", "note": '{"phase": "quality_assessment", "quality_assessment": {"total": 5.5}, "audit_version": "1.2"}'}}
    
    mock_gateway.get_item_children.return_value = [note_ta, note_ft, note_qa]
    
    phase = orchestrator.resolve_target_phase(item_key, default_qa_threshold=5.0)
    assert phase == "quality_assessment"

def test_get_promotion_path(orchestrator, mock_gateway):
    parent_key = "ROOT"
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "ROOT"}},
        {"key": "C2", "data": {"name": "2-fulltext", "parentCollection": "ROOT"}}
    ]
    
    # Promote to full_text
    src, dest = orchestrator.get_promotion_path(parent_key, "full_text")
    assert src == "C1"
    assert dest == "C2"
    
    # Promote to title_abstract
    src, dest = orchestrator.get_promotion_path(parent_key, "title_abstract")
    assert src == parent_key
    assert dest == "C1"
