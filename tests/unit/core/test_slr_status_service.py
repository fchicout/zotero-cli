from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.slr.status_service import SLRStatusService


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock()
    # Provide the real flow definition so the service can iterate
    from zotero_cli.core.services.slr.orchestrator import SLROrchestrator

    orchestrator.PHASE_FLOW = SLROrchestrator.PHASE_FLOW
    return orchestrator


@pytest.fixture
def service(mock_gateway, mock_orchestrator):
    return SLRStatusService(mock_gateway, mock_orchestrator)


def test_get_slr_status_simple(service, mock_gateway):
    # Setup 1 raw collection
    mock_gateway.get_all_collections.return_value = [
        {"key": "RAW1", "data": {"name": "raw_test", "parentCollection": None}}
    ]
    # Setup subfolders
    mock_gateway.get_all_collections.return_value.extend(
        [
            {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "RAW1"}},
        ]
    )

    # Mock items in folders
    mock_gateway.get_items_in_collection.return_value = []  # Empty for simplicity

    results = service.get_slr_status()

    assert len(results) == 1
    assert results[0].source_name == "raw_test"
    assert "title_abstract" in results[0].phases


def test_get_phase_decision_logic(service, mock_gateway):
    # Test internal helper directly if possible or via integration
    children = [
        {
            "data": {
                "itemType": "note",
                "note": '{"phase": "full_text", "decision": "rejected", "audit_version": "1.2"}',
            }
        }
    ]

    decision = service._get_phase_decision(children, "full_text")
    assert decision == "rejected"

    decision = service._get_phase_decision(children, "title_abstract")
    assert decision is None


def test_phase_decision_empty_string_returns_none(service):
    """Empty decision field must return None, not '', so the item counts as pending."""
    children = [
        {
            "data": {
                "itemType": "note",
                "note": '{"phase": "title_abstract", "decision": "", "audit_version": "1.2"}',
            }
        }
    ]
    decision = service._get_phase_decision(children, "title_abstract")
    # Must be None (pending) not "" (which would silently exclude from all counts)
    assert decision is None


def test_qa_note_no_score_falls_back_to_decision_field(service):
    """QA note with no total score should fall back to the decision field."""
    children = [
        {
            "data": {
                "itemType": "note",
                "note": '{"phase": "quality_assessment", "decision": "accepted", "audit_version": "1.2"}',
            }
        }
    ]
    decision = service._get_phase_decision(children, "quality_assessment")
    assert decision == "accepted"


def test_qa_note_no_score_no_decision_returns_none(service):
    """QA note with no score and no decision field must return None (counts as pending)."""
    children = [
        {
            "data": {
                "itemType": "note",
                "note": '{"phase": "quality_assessment", "quality_assessment": {}, "audit_version": "1.2"}',
            }
        }
    ]
    decision = service._get_phase_decision(children, "quality_assessment")
    assert decision is None


def test_qa_note_with_score_below_threshold_is_rejected(service):
    """QA note with total score below threshold must count as rejected."""
    children = [
        {
            "data": {
                "itemType": "note",
                "note": '{"phase": "quality_assessment", "quality_assessment": {"total": 1.0, "limit": 2.0}, "audit_version": "1.2"}',
            }
        }
    ]
    decision = service._get_phase_decision(children, "quality_assessment")
    assert decision == "rejected"


def test_qa_note_with_score_above_threshold_is_accepted(service):
    """QA note with total score at or above threshold must count as accepted."""
    children = [
        {
            "data": {
                "itemType": "note",
                "note": '{"phase": "quality_assessment", "quality_assessment": {"total": 3.0, "limit": 2.0}, "audit_version": "1.2"}',
            }
        }
    ]
    decision = service._get_phase_decision(children, "quality_assessment")
    assert decision == "accepted"

