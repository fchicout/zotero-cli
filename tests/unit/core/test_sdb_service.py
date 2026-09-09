from unittest.mock import Mock

import pytest

from zotero_cli.core.services.sdb.sdb_service import SDBService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock()


@pytest.fixture
def service(mock_gateway):
    return SDBService(mock_gateway)


def _note_child(key, version, decision, persona="P1", phase="ph1", reason_code=None):
    payload = {
        "audit_version": "1.2",
        "decision": decision,
        "persona": persona,
        "phase": phase,
    }
    if reason_code is not None:
        payload["reason_code"] = reason_code
    import json

    return {
        "key": key,
        "version": version,
        "data": {"itemType": "note", "note": f"<div>{json.dumps(payload)}</div>"},
    }


def _item(key, tags=None):
    return ZoteroItem(key=key, version=1, item_type="journalArticle", tags=tags or [])


def test_inspect_item_sdb(service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {
            "key": "N1",
            "version": 10,
            "data": {
                "itemType": "note",
                "note": '<div>{"audit_version": "1.2", "decision": "accepted", "persona": "P1", "phase": "ph1"}</div>',
            },
        },
        {"key": "N2", "data": {"itemType": "note", "note": "regular note"}},
    ]

    entries = service.inspect_item_sdb("ITEM1")
    assert len(entries) == 1
    assert entries[0]["decision"] == "accepted"
    assert entries[0]["_note_key"] == "N1"
    assert entries[0]["_note_version"] == 10


def test_classify_decision_agreement_unscreened(service, mock_gateway):
    mock_gateway.get_item_children.return_value = []
    assert service.classify_decision_agreement(["I1", "I2"]) == "UNSCREENED"


def test_classify_decision_agreement_matching(service, mock_gateway):
    def children_for(item_key):
        return [
            {
                "key": f"N-{item_key}",
                "version": 1,
                "data": {
                    "itemType": "note",
                    "note": '<div>{"audit_version": "1.2", "decision": "accepted"}</div>',
                },
            }
        ]

    mock_gateway.get_item_children.side_effect = children_for
    assert service.classify_decision_agreement(["I1", "I2"]) == "MATCHING"


def test_classify_decision_agreement_conflicting(service, mock_gateway):
    def children_for(item_key):
        decision = "accepted" if item_key == "I1" else "rejected"
        return [
            {
                "key": f"N-{item_key}",
                "version": 1,
                "data": {
                    "itemType": "note",
                    "note": f'<div>{{"audit_version": "1.2", "decision": "{decision}"}}</div>',
                },
            }
        ]

    mock_gateway.get_item_children.side_effect = children_for
    assert service.classify_decision_agreement(["I1", "I2"]) == "CONFLICTING"


def test_build_inspect_table(service):
    entries = [
        {
            "decision": "accepted",
            "persona": "P1",
            "phase": "ph1",
            "audit_version": "1.2",
            "timestamp": "2026-01-01",
        }
    ]
    table = service.build_inspect_table("ITEM1", entries)
    assert table.title == "SDB Inspect: ITEM1"
    assert len(table.rows) == 1


def test_edit_sdb_entry_success(service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {
            "key": "N1",
            "version": 10,
            "data": {
                "itemType": "note",
                "note": '<div>{"audit_version": "1.2", "decision": "accepted", "persona": "P1", "phase": "ph1"}</div>',
            },
        }
    ]
    mock_gateway.update_note.return_value = True

    success, msg = service.edit_sdb_entry(
        "ITEM1", "P1", "ph1", {"decision": "rejected"}, dry_run=False
    )

    assert success is True
    assert "Successfully updated" in msg
    mock_gateway.update_note.assert_called_once()
    args = mock_gateway.update_note.call_args[0]
    assert args[0] == "N1"
    assert '"decision": "rejected"' in args[2]


def test_edit_sdb_entry_not_found(service, mock_gateway):
    mock_gateway.get_item_children.return_value = []
    success, msg = service.edit_sdb_entry("ITEM1", "P1", "ph1", {"decision": "rejected"})
    assert success is False
    assert "No SDB entry found" in msg


def test_upgrade_sdb_entries(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_item = Mock()
    mock_item.key = "ITEM1"
    mock_gateway.get_items_in_collection.return_value = [mock_item]

    mock_gateway.get_item_children.return_value = [
        {
            "key": "N1",
            "version": 10,
            "data": {
                "itemType": "note",
                "note": '<div>{"audit_version": "1.0", "decision": "accepted", "persona": "P1", "phase": "ph1", "comment": "Old comment"}</div>',
            },
        }
    ]
    mock_gateway.update_note.return_value = True

    stats = service.upgrade_sdb_entries("Collection1", dry_run=False)

    assert stats["scanned"] == 1
    assert stats["upgraded"] == 1
    mock_gateway.update_note.assert_called_once()
    args = mock_gateway.update_note.call_args[0]
    assert '"audit_version": "1.2"' in args[2]
    assert '"reason_text": "Old comment"' in args[2]


# --- filter_items_by_sdb (Issue #294) ---


def test_filter_items_by_sdb_included_matches(service, mock_gateway):
    item = _item("I1", tags=["rsl:include"])
    mock_gateway.get_item_children.return_value = [_note_child("N1", 1, "accepted")]

    results = service.filter_items_by_sdb([item], included=True)

    assert len(results) == 1
    assert results[0][0] is item
    assert results[0][1]["decision"] == "accepted"


def test_filter_items_by_sdb_included_skips_untagged_item_without_deep_scan(
    service, mock_gateway
):
    """The tag fast-filter must short-circuit before the deep note scan -
    an item missing the rsl:include tag should never trigger
    get_item_children at all."""
    item = _item("I1", tags=[])

    results = service.filter_items_by_sdb([item], included=True)

    assert results == []
    mock_gateway.get_item_children.assert_not_called()


def test_filter_items_by_sdb_excluded_requires_exclude_tag_and_rejected_decision(
    service, mock_gateway
):
    matching_item = _item("I1", tags=["rsl:exclude:IC1"])
    mock_gateway.get_item_children.return_value = [_note_child("N1", 1, "rejected")]

    results = service.filter_items_by_sdb([matching_item], excluded=True)

    assert len(results) == 1
    assert results[0][1]["decision"] == "rejected"


def test_filter_items_by_sdb_excluded_no_exclude_tag_is_skipped(service, mock_gateway):
    item = _item("I1", tags=["rsl:include"])

    results = service.filter_items_by_sdb([item], excluded=True)

    assert results == []
    mock_gateway.get_item_children.assert_not_called()


def test_filter_items_by_sdb_criteria_matches_reason_code(service, mock_gateway):
    item = _item("I1", tags=["rsl:exclude:IC2"])
    mock_gateway.get_item_children.return_value = [
        _note_child("N1", 1, "rejected", reason_code=["IC1", "IC2"])
    ]

    results = service.filter_items_by_sdb([item], criteria="IC2")

    assert len(results) == 1


def test_filter_items_by_sdb_criteria_not_in_entry_reason_code_excludes_item(
    service, mock_gateway
):
    item = _item("I1", tags=["rsl:exclude:IC2"])
    mock_gateway.get_item_children.return_value = [
        _note_child("N1", 1, "rejected", reason_code=["IC3"])
    ]

    results = service.filter_items_by_sdb([item], criteria="IC2")

    assert results == []


def test_filter_items_by_sdb_persona_filter_matches(service, mock_gateway):
    item = _item("I1")
    mock_gateway.get_item_children.return_value = [
        _note_child("N1", 1, "accepted", persona="Orion")
    ]

    results = service.filter_items_by_sdb([item], persona="Orion")

    assert len(results) == 1


def test_filter_items_by_sdb_persona_filter_excludes_non_matching_entry(service, mock_gateway):
    item = _item("I1")
    mock_gateway.get_item_children.return_value = [
        _note_child("N1", 1, "accepted", persona="Silas")
    ]

    results = service.filter_items_by_sdb([item], persona="Orion")

    assert results == []


def test_filter_items_by_sdb_phase_filter_matches(service, mock_gateway):
    item = _item("I1")
    mock_gateway.get_item_children.return_value = [
        _note_child("N1", 1, "accepted", phase="full_text")
    ]

    results = service.filter_items_by_sdb([item], phase="full_text")

    assert len(results) == 1


def test_filter_items_by_sdb_phase_filter_excludes_non_matching_entry(service, mock_gateway):
    item = _item("I1")
    mock_gateway.get_item_children.return_value = [
        _note_child("N1", 1, "accepted", phase="title_abstract")
    ]

    results = service.filter_items_by_sdb([item], phase="full_text")

    assert results == []


def test_filter_items_by_sdb_picks_first_matching_entry_among_several(service, mock_gateway):
    item = _item("I1")
    mock_gateway.get_item_children.return_value = [
        _note_child("N1", 1, "rejected", persona="Silas"),
        _note_child("N2", 2, "accepted", persona="Orion"),
    ]

    results = service.filter_items_by_sdb([item], persona="Orion")

    assert len(results) == 1
    assert results[0][1]["_note_key"] == "N2"


def test_filter_items_by_sdb_no_deep_match_excludes_item(service, mock_gateway):
    """An item with an SDB note that fails every deep-filter condition
    must be excluded from the results, not included with no matched
    entry."""
    item = _item("I1")
    mock_gateway.get_item_children.return_value = [_note_child("N1", 1, "rejected")]

    results = service.filter_items_by_sdb([item], included=True)

    assert results == []


def test_filter_items_by_sdb_combines_multiple_filters(service, mock_gateway):
    item = _item("I1", tags=["rsl:exclude:IC1"])
    mock_gateway.get_item_children.return_value = [
        _note_child("N1", 1, "rejected", persona="Orion", phase="full_text", reason_code=["IC1"])
    ]

    results = service.filter_items_by_sdb(
        [item], excluded=True, criteria="IC1", persona="Orion", phase="full_text"
    )

    assert len(results) == 1
