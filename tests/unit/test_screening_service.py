from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def screening_service(mock_gateway):
    # Pass mock_gateway for all repo interfaces since it implements them all
    # For collection_service, we use a mock
    mock_col_service = MagicMock()
    return ScreeningService(
        mock_gateway, mock_gateway, mock_gateway, mock_gateway, mock_col_service
    )


def test_record_decision_success(screening_service, mock_gateway):
    item_key = "ITEM123"
    mock_gateway.create_note.return_value = True
    mock_gateway.get_item_children.return_value = []

    success = screening_service.record_decision(
        item_key=item_key, decision="INCLUDE", code="IC1", reason="Relevant study"
    )

    assert success is True
    # Verify note creation
    args, _ = mock_gateway.create_note.call_args
    assert args[0] == item_key
    note_content = args[1]
    assert "screening_decision" in note_content
    assert "accepted" in note_content
    assert '"reason_code": []' in note_content  # Forced empty for inclusions
    assert "Relevant study" in note_content
    assert "audit_version" in note_content
    assert "1.2" in note_content


def test_record_decision_with_evidence(screening_service, mock_gateway):
    item_key = "ITEM123"
    mock_gateway.create_note.return_value = True
    mock_gateway.get_item_children.return_value = []

    success = screening_service.record_decision(
        item_key=item_key,
        decision="INCLUDE",
        code="IC1",
        evidence="Found direct quote on page 5: 'Performance improved by 20%'.",
    )

    assert success is True
    args, _ = mock_gateway.create_note.call_args
    note_content = args[1]
    assert '"reason_code": []' in note_content  # Forced empty
    assert "Found direct quote on page 5" in note_content
    assert '"evidence":' in note_content


def test_record_decision_exclude_preserves_code(screening_service, mock_gateway):
    item_key = "ITEM123"
    mock_gateway.create_note.return_value = True
    mock_gateway.get_item_children.return_value = []

    success = screening_service.record_decision(
        item_key=item_key, decision="EXCLUDE", code="EC1", reason="Out of scope"
    )

    assert success is True
    args, _ = mock_gateway.create_note.call_args
    note_content = args[1]
    # Check for "EC1" in reason_code list
    assert '"EC1"' in note_content
    assert "rejected" in note_content


def test_record_decision_with_move(screening_service, mock_gateway):
    item_key = "ITEM123"
    source_col = "Raw"
    target_col = "Screened"

    mock_gateway.create_note.return_value = True
    mock_gateway.get_item_children.return_value = []

    # Mock the internal collection service
    screening_service.collection_service.move_item.return_value = True

    success = screening_service.record_decision(
        item_key=item_key,
        decision="EXCLUDE",
        code="EC1",
        source_collection=source_col,
        target_collection=target_col,
    )

    assert success is True
    # Verify move delegated to collection service
    screening_service.collection_service.move_item.assert_called_once_with(
        source_col, target_col, item_key
    )


def test_record_decision_note_does_not_apply_tags_or_move(screening_service, mock_gateway):
    """Issue #201: record_decision_note is the note-only primitive - no
    shared tags, no collection movement, safe to call per-persona."""
    item_key = "ITEM123"
    mock_gateway.create_note.return_value = True
    mock_gateway.get_item_children.return_value = []

    success = screening_service.record_decision_note(
        item_key=item_key, decision="INCLUDE", code="", persona="rater_a"
    )

    assert success is True
    mock_gateway.create_note.assert_called_once()
    mock_gateway.add_tags.assert_not_called()
    screening_service.collection_service.move_item.assert_not_called()


def test_record_decision_note_upserts_per_persona(screening_service, mock_gateway):
    """Two personas screening the same item each get their own independent
    note - neither overwrites the other's decision (Issue #201)."""
    item_key = "ITEM123"
    mock_gateway.create_note.return_value = True
    # No existing notes for either persona yet
    mock_gateway.get_item_children.return_value = []

    screening_service.record_decision_note(
        item_key=item_key, decision="INCLUDE", code="", persona="rater_a"
    )
    screening_service.record_decision_note(
        item_key=item_key, decision="EXCLUDE", code="EC1", persona="rater_b"
    )

    assert mock_gateway.create_note.call_count == 2
    # Neither call should have triggered an update (no existing note found)
    mock_gateway.update_note.assert_not_called()


def test_apply_decision_outcome_applies_tags_and_move_without_writing_note(
    screening_service, mock_gateway
):
    """Issue #201: apply_decision_outcome is the outcome-only primitive -
    tags + move, no note write, callable once after reconciliation."""
    item_key = "ITEM123"
    screening_service.collection_service.move_item.return_value = True
    mock_gateway.add_tags.return_value = True

    success = screening_service.apply_decision_outcome(
        item_key=item_key,
        decision="EXCLUDE",
        code="EC1",
        source_collection="Raw",
        target_collection="Excluded",
    )

    assert success is True
    mock_gateway.create_note.assert_not_called()
    mock_gateway.update_note.assert_not_called()
    tags_arg = mock_gateway.add_tags.call_args.args[1]
    assert "rsl:exclude:EC1" in tags_arg
    screening_service.collection_service.move_item.assert_called_once_with(
        "Raw", "Excluded", item_key
    )


def test_apply_decision_outcome_invalid_decision(screening_service):
    assert screening_service.apply_decision_outcome("K1", "MAYBE", "") is False


def test_get_decisions_for_item_returns_every_persona(screening_service, mock_gateway):
    """Issue #201: get_decisions_for_item surfaces what each persona
    decided, not just whether any decision exists."""
    mock_gateway.get_item_children.return_value = [
        {
            "data": {
                "itemType": "note",
                "note": (
                    '<div>{"action": "screening_decision", "audit_version": "1.2", '
                    '"decision": "accepted", "persona": "rater_a", "phase": "title_abstract"}</div>'
                ),
            }
        },
        {
            "data": {
                "itemType": "note",
                "note": (
                    '<div>{"action": "screening_decision", "audit_version": "1.2", '
                    '"decision": "rejected", "persona": "rater_b", "phase": "title_abstract"}</div>'
                ),
            }
        },
        {"data": {"itemType": "attachment"}},  # non-note child, ignored
    ]

    decisions = screening_service.get_decisions_for_item("ITEM123")

    assert len(decisions) == 2
    personas = {d["persona"] for d in decisions}
    assert personas == {"rater_a", "rater_b"}
    decisions_by_persona = {d["persona"]: d["decision"] for d in decisions}
    assert decisions_by_persona["rater_a"] == "accepted"
    assert decisions_by_persona["rater_b"] == "rejected"


def test_get_decisions_for_item_no_notes(screening_service, mock_gateway):
    mock_gateway.get_item_children.return_value = []
    assert screening_service.get_decisions_for_item("ITEM123") == []


def test_double_blind_two_personas_then_reconciled_outcome(screening_service, mock_gateway):
    """End-to-end double-blind scenario (Issue #201): two raters disagree,
    recording their decisions independently must not touch shared item
    state; only the explicit reconciliation call applies the final tags."""
    item_key = "ITEM123"
    mock_gateway.create_note.return_value = True
    mock_gateway.get_item_children.return_value = []

    # Rater A includes, rater B excludes - recorded independently.
    assert screening_service.record_decision_note(
        item_key, "INCLUDE", "", persona="rater_a"
    )
    assert screening_service.record_decision_note(
        item_key, "EXCLUDE", "EC1", persona="rater_b"
    )

    # Neither independent call should have mutated shared item state.
    mock_gateway.add_tags.assert_not_called()
    screening_service.collection_service.move_item.assert_not_called()

    # A tie-breaker reconciles: final outcome is EXCLUDE. Only now do the
    # shared tags/move fire, exactly once.
    mock_gateway.add_tags.return_value = True
    screening_service.collection_service.move_item.return_value = True
    assert screening_service.apply_decision_outcome(
        item_key,
        "EXCLUDE",
        "EC1",
        source_collection="Raw",
        target_collection="Excluded",
    )

    mock_gateway.add_tags.assert_called_once()
    screening_service.collection_service.move_item.assert_called_once_with(
        "Raw", "Excluded", item_key
    )


def test_get_pending_items(screening_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "COL_ID"

    item1 = ZoteroItem(key="I1", version=1, item_type="journalArticle")
    item2 = ZoteroItem(key="I2", version=1, item_type="journalArticle")
    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])

    # item1 has decision note, item2 does not
    mock_gateway.get_item_children.side_effect = [
        [{"itemType": "note", "note": "screening_decision JSON ..."}],
        [],
    ]

    pending = screening_service.get_pending_items("Any")

    assert len(pending) == 1
    assert pending[0].key == "I2"
