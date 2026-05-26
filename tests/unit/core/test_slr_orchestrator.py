from unittest.mock import MagicMock

import pytest

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
    from typing import Any, Dict, List

    parent_key = "ROOT"
    all_cols: List[Dict[str, Any]] = []
    mock_gateway.create_collection.side_effect = ["NEW1", "NEW2", "NEW3", "NEW4"]

    phase_map = orchestrator.ensure_slr_hierarchy(parent_key, all_cols)

    assert len(phase_map) == 4
    assert phase_map["1-title_abstract"] == "NEW1"
    assert mock_gateway.create_collection.call_count == 4


def test_resolve_target_phase_sequential(orchestrator, mock_gateway):
    item_key = "ITEM"
    # Notes for T&A and FT with SDB markers
    note_ta = {
        "data": {
            "itemType": "note",
            "note": '{"phase": "title_abstract", "decision": "accepted", "audit_version": "1.2"}',
        }
    }
    note_ft = {
        "data": {
            "itemType": "note",
            "note": '{"phase": "full_text", "decision": "accepted", "audit_version": "1.2"}',
        }
    }
    note_qa = {
        "data": {
            "itemType": "note",
            "note": '{"phase": "quality_assessment", "quality_assessment": {"total": 1.0}, "audit_version": "1.2"}',
        }
    }  # Failed QA (default 2.0)

    mock_gateway.get_item_children.return_value = [note_ta, note_ft, note_qa]

    phase = orchestrator.resolve_target_phase(item_key, default_qa_threshold=2.0)
    assert phase == "full_text"


def test_resolve_target_phase_qa_success(orchestrator, mock_gateway):
    item_key = "ITEM"
    note_ta = {
        "data": {
            "itemType": "note",
            "note": '{"phase": "title_abstract", "decision": "accepted", "audit_version": "1.2"}',
        }
    }
    note_ft = {
        "data": {
            "itemType": "note",
            "note": '{"phase": "full_text", "decision": "accepted", "audit_version": "1.2"}',
        }
    }
    note_qa = {
        "data": {
            "itemType": "note",
            "note": '{"phase": "quality_assessment", "quality_assessment": {"total": 5.5}, "audit_version": "1.2"}',
        }
    }

    mock_gateway.get_item_children.return_value = [note_ta, note_ft, note_qa]

    phase = orchestrator.resolve_target_phase(item_key, default_qa_threshold=5.0)
    assert phase == "quality_assessment"


def test_get_promotion_path(orchestrator, mock_gateway):
    parent_key = "ROOT"
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "ROOT"}},
        {"key": "C2", "data": {"name": "2-fulltext", "parentCollection": "ROOT"}},
    ]

    # Promote to full_text
    src, dest = orchestrator.get_promotion_path(parent_key, "full_text")
    assert src == "C1"
    assert dest == "C2"

    # Promote to title_abstract
    src, dest = orchestrator.get_promotion_path(parent_key, "title_abstract")
    assert src == parent_key
    assert dest == "C1"


def test_ensure_slr_hierarchy_all_cols_none(orchestrator, mock_gateway):
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "ROOT"}}
    ]
    phase_map = orchestrator.ensure_slr_hierarchy("ROOT")
    assert phase_map["1-title_abstract"] == "C1"


def test_get_folder_key_for_phase(orchestrator, mock_gateway):
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "ROOT"}}
    ]
    key = orchestrator.get_folder_key_for_phase("ROOT", "title_abstract")
    assert key == "C1"

    key_none = orchestrator.get_folder_key_for_phase("ROOT", None)
    assert key_none == "ROOT"


def test_record_duplicate_resolution(orchestrator, mock_gateway):
    # record resolution
    mock_gateway.create_note.return_value = "NOTE123"
    orchestrator.record_duplicate_resolution("I1", "I2", "Exact match")
    mock_gateway.create_note.assert_called_once()


def test_get_all_papers_in_tree(orchestrator, mock_gateway):
    mock_gateway.get_all_collections.return_value = [
        {"key": "ROOT", "data": {"name": "raw_test", "parentCollection": None}},
        {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "ROOT"}},
        {"key": "C2", "data": {"name": "2-fulltext", "parentCollection": "ROOT"}},
        {"key": "C3", "data": {"name": "3-quality_assessment", "parentCollection": "ROOT"}},
        {"key": "C4", "data": {"name": "4-data_extraction", "parentCollection": "ROOT"}},
    ]

    paper1 = MagicMock()
    paper1.key = "P1"
    paper1.item_type = "document"
    paper2 = MagicMock()
    paper2.key = "P2"
    paper2.item_type = "document"
    paper3 = MagicMock()
    paper3.key = "P3"
    paper3.item_type = "document"

    mock_gateway.get_items_in_collection.side_effect = [
        [paper1],  # root
        [paper2],  # C1
        [paper3],  # C2
        [],        # C3
        []         # C4
    ]

    papers = orchestrator.get_all_papers_in_tree("ROOT")
    assert len(papers) == 3
    assert {p.key for p in papers} == {"P1", "P2", "P3"}


def test_reconcile_qa_audit_success(orchestrator, mock_gateway):
    mock_note = {
        "key": "N123",
        "version": 5,
        "data": {
            "itemType": "note",
            "note": '{"phase": "quality_assessment", "decision": "rejected", "audit_version": "1.2"}'
        }
    }
    mock_gateway.get_item_children.return_value = [mock_note]
    mock_gateway.update_note.return_value = True

    res = orchestrator.reconcile_qa_audit("I1", 3.0, "accepted", "reconciler")
    assert res is True
    mock_gateway.update_note.assert_called_once()


def test_reconcile_qa_audit_not_found(orchestrator, mock_gateway):
    mock_gateway.get_item_children.return_value = []
    res = orchestrator.reconcile_qa_audit("I1", 3.0, "accepted", "reconciler")
    assert res is False



