from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.slr.status_service import SLRStatusService


@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def service(mock_gateway):
    return SLRStatusService(mock_gateway)

def test_get_slr_status_simple(service, mock_gateway):
    # Setup 1 raw collection
    mock_gateway.get_all_collections.return_value = [
        {"key": "RAW1", "data": {"name": "raw_test", "parentCollection": None}}
    ]
    # Setup subfolders
    mock_gateway.get_all_collections.return_value.extend([
        {"key": "C1", "data": {"name": "1-title_abstract", "parentCollection": "RAW1"}},
    ])

    # Mock items in folders
    mock_gateway.get_items_in_collection.return_value = [] # Empty for simplicity

    results = service.get_slr_status()

    assert len(results) == 1
    assert results[0].source_name == "raw_test"
    assert "title_abstract" in results[0].phases

def test_get_phase_decision_logic(service, mock_gateway):
    # Test internal helper directly if possible or via integration
    children = [
        {"data": {"itemType": "note", "note": '{"phase": "full_text", "decision": "rejected", "audit_version": "1.2"}'}}
    ]

    decision = service._get_phase_decision(children, "full_text")
    assert decision == "rejected"

    decision = service._get_phase_decision(children, "title_abstract")
    assert decision is None
