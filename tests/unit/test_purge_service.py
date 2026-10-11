from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.purge_service import PurgeService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def purge_service(mock_gateway):
    return PurgeService(mock_gateway)


class _CountingGateway(MagicMock):
    """An online gateway that reports how many items of a type exist, so
    the scan-or-lookup choice can be made (Issue #441)."""

    total = 150  # 2 pages: a scan beats 3+ per-parent lookups

    def count_search_results(self, query):
        self.counted.append(query.item_type)
        return type(self).total


@pytest.fixture
def scan_gateway():
    gateway = _CountingGateway()
    gateway.counted = []
    return gateway


def test_purge_attachments_dry_run(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 1}},
        {"key": "N1", "data": {"itemType": "note", "version": 1}},
    ]

    stats = purge_service.purge_attachments(["P1"], dry_run=True)

    assert stats["skipped"] == 1
    assert stats["deleted"] == 0
    mock_gateway.delete_item.assert_not_called()


def test_purge_attachments_execute(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 5}}
    ]
    mock_gateway.delete_item.return_value = True

    stats = purge_service.purge_attachments(["P1"], dry_run=False)

    assert stats["deleted"] == 1
    mock_gateway.delete_item.assert_called_once_with("A1", 5)


def test_purge_tags_all(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=10, item_type="journalArticle", tags=["t1", "t2"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = True

    stats = purge_service.purge_tags(["K1"], dry_run=False)

    assert stats["deleted"] == 1
    mock_gateway.update_item_metadata.assert_called_once_with("K1", 10, {"tags": []})


def test_purge_tags_specific(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=10, item_type="journalArticle", tags=["t1", "t2"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = True

    stats = purge_service.purge_tags(["K1"], tag_name="t1", dry_run=False)

    assert stats["deleted"] == 1
    mock_gateway.update_item_metadata.assert_called_once_with("K1", 10, {"tags": [{"tag": "t2"}]})


def test_offline_veto(purge_service, mock_gateway):
    # Mocking the class name to trigger _is_offline
    mock_gateway.__class__.__name__ = "SqliteZoteroGateway"

    with pytest.raises(RuntimeError, match="Offline Veto"):
        purge_service.purge_attachments(["K1"])


def test_purge_attachments_error(purge_service, mock_gateway):
    mock_gateway.get_item_children.side_effect = Exception("API Error")
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_tags_item_not_found(purge_service, mock_gateway):
    mock_gateway.get_item.return_value = None
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_tags_api_failure(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = False

    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_attachments_error_handling(purge_service, mock_gateway):
    mock_gateway.get_item_children.side_effect = Exception("Network error")
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_attachments_delete_failure(purge_service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 5}}
    ]
    mock_gateway.delete_item.return_value = False
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_notes_error_handling(purge_service, mock_gateway):
    mock_gateway.get_item_children.side_effect = Exception("Network error")
    stats = purge_service.purge_notes(["P1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_tags_no_tags(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=[])
    mock_gateway.get_item.return_value = item
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["deleted"] == 0


def test_purge_tags_not_present(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t2"])
    mock_gateway.get_item.return_value = item
    stats = purge_service.purge_tags(["K1"], tag_name="t1", dry_run=False)
    assert stats["deleted"] == 0


def test_purge_tags_update_failure(purge_service, mock_gateway):
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = False
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_attachments_alternate_key(purge_service, mock_gateway):
    # Test line 46: key = child.get("key") or data.get("key")
    mock_gateway.get_item_children.return_value = [
        {"data": {"itemType": "attachment", "version": 5, "key": "A1"}}
    ]
    mock_gateway.delete_item.return_value = True
    stats = purge_service.purge_attachments(["P1"], dry_run=False)
    assert stats["deleted"] == 1


def test_purge_notes_alternate_key(purge_service, mock_gateway):
    # Test line 83: key = child.get("key") or data.get("key")
    mock_gateway.get_item_children.return_value = [
        {"data": {"itemType": "note", "version": 5, "key": "N1"}}
    ]
    mock_gateway.delete_item.return_value = True
    stats = purge_service.purge_notes(["P1"], dry_run=False)
    assert stats["deleted"] == 1


def test_purge_tags_all_branch(purge_service, mock_gateway):
    # Test line 123: else: new_tags = []
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    mock_gateway.update_item_metadata.return_value = True
    stats = purge_service.purge_tags(["K1"], tag_name=None, dry_run=False)
    assert stats["deleted"] == 1


def test_offline_veto_notes(purge_service, mock_gateway):
    # Test line 61
    mock_gateway.__class__.__name__ = "SqliteZoteroGateway"
    with pytest.raises(RuntimeError, match="Offline Veto"):
        purge_service.purge_notes(["K1"])


def test_offline_veto_tags(purge_service, mock_gateway):
    # Test line 101
    mock_gateway.__class__.__name__ = "SqliteZoteroGateway"
    with pytest.raises(RuntimeError, match="Offline Veto"):
        purge_service.purge_tags(["K1"])


def test_purge_notes_dry_run(purge_service, mock_gateway):
    # Test line 83
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "version": 1}}
    ]
    stats = purge_service.purge_notes(["P1"], dry_run=True)
    assert stats["skipped"] == 1


def test_purge_notes_delete_failure(purge_service, mock_gateway):
    # Test line 88
    mock_gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note", "version": 1}}
    ]
    mock_gateway.delete_item.return_value = False
    stats = purge_service.purge_notes(["P1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_tags_dry_run(purge_service, mock_gateway):
    # Test line 123
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item
    stats = purge_service.purge_tags(["K1"], dry_run=True)
    assert stats["skipped"] == 1


def test_purge_tags_exception_line_131(purge_service, mock_gateway):
    # Ensure line 131 is hit
    mock_gateway.get_item.side_effect = Exception("Crash")
    stats = purge_service.purge_tags(["K1"], dry_run=False)
    assert stats["errors"] == 1


def test_purge_item_assets(purge_service, mock_gateway):
    # Setup for multiple assets
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 1}},
        {"key": "N1", "data": {"itemType": "note", "version": 1}},
    ]
    item = ZoteroItem(key="P1", version=1, item_type="journalArticle", tags=["t1"])
    mock_gateway.get_item.return_value = item

    mock_gateway.delete_item.return_value = True
    mock_gateway.update_item_metadata.return_value = True

    # Execute for all types
    stats = purge_service.purge_item_assets("P1", types=["files", "notes", "tags"], dry_run=False)

    assert stats["deleted"] == 3  # 1 attachment, 1 note, 1 tag update

    # Verify calls
    mock_gateway.delete_item.assert_any_call("A1", 1)
    mock_gateway.delete_item.assert_any_call("N1", 1)
    mock_gateway.update_item_metadata.assert_called_with("P1", 1, {"tags": []})


def test_purge_collection_assets(purge_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "C1"

    item1 = ZoteroItem(key="P1", version=1, item_type="journalArticle", tags=["t1"])
    item2 = ZoteroItem(key="P2", version=1, item_type="journalArticle", tags=[])

    mock_gateway.get_items_in_collection.return_value = [item1, item2]

    # Setup item children (attachments/notes) for P1 and P2
    # This mock needs to handle multiple calls differently if we want precise accounting,
    # but for simple verification, we can just return a fixed list or use side_effect.
    # P1 has 1 attachment. P2 has none.
    def get_children(key):
        if key == "P1":
            return [{"key": "A1", "data": {"itemType": "attachment", "version": 1}}]
        return []

    mock_gateway.get_item_children.side_effect = get_children

    # P1 has tags. P2 has none.
    def get_item(key):
        if key == "P1":
            return item1
        return item2

    mock_gateway.get_item.side_effect = get_item

    mock_gateway.delete_item.return_value = True
    mock_gateway.update_item_metadata.return_value = True

    stats = purge_service.purge_collection_assets(
        "TestCollection", types=["files", "tags"], dry_run=False
    )

    # P1: 1 attachment deleted, 1 tag update = 2
    # P2: 0 attachments, 0 tags = 0
    assert stats["deleted"] == 2

    mock_gateway.get_collection_id_by_name.assert_called_with("TestCollection")
    mock_gateway.get_items_in_collection.assert_called_with("C1", top_only=True)


def test_purge_collection_not_found(purge_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = None
    stats = purge_service.purge_collection_assets("Unknown", dry_run=False)
    assert stats["errors"] == 1


def _attachment_item(key, parent_item, version=1):
    raw = {"key": key, "data": {"itemType": "attachment", "version": version, "key": key}}
    return ZoteroItem(
        key=key, version=version, item_type="attachment", parent_item=parent_item, raw_data=raw
    )


def _note_item(key, parent_item, note="", version=1):
    raw = {
        "key": key,
        "data": {"itemType": "note", "version": version, "key": key, "note": note},
    }
    return ZoteroItem(
        key=key, version=version, item_type="note", parent_item=parent_item, raw_data=raw
    )


def test_purge_attachments_batches_scan_for_many_parents(scan_gateway):
    """Regression test for Issue #276: with more than a couple of parent
    keys, purge_attachments must do one search_items(item_type=...) scan
    instead of one get_item_children round-trip per parent."""
    mock_gateway = scan_gateway
    purge_service = PurgeService(scan_gateway)
    mock_gateway.search_items.return_value = [
        _attachment_item("A1", "P1"),
        _attachment_item("A2", "P2"),
        _attachment_item("A3", "OTHER"),  # not one of the requested parents
    ]
    mock_gateway.delete_item.return_value = True

    stats = purge_service.purge_attachments(["P1", "P2", "P3"], dry_run=False)

    assert stats["deleted"] == 2
    mock_gateway.get_item_children.assert_not_called()
    mock_gateway.search_items.assert_called_once()
    query = mock_gateway.search_items.call_args[0][0]
    assert query.item_type == "attachment"
    mock_gateway.delete_item.assert_any_call("A1", 1)
    mock_gateway.delete_item.assert_any_call("A2", 1)


def test_purge_notes_batches_scan_for_many_parents(scan_gateway):
    """Regression test for Issue #276, notes path."""
    mock_gateway = scan_gateway
    purge_service = PurgeService(scan_gateway)
    mock_gateway.search_items.return_value = [
        _note_item("N1", "P1"),
        _note_item("N2", "P2"),
    ]
    mock_gateway.delete_item.return_value = True

    stats = purge_service.purge_notes(["P1", "P2", "P3"], dry_run=False)

    assert stats["deleted"] == 2
    mock_gateway.get_item_children.assert_not_called()
    mock_gateway.search_items.assert_called_once()
    query = mock_gateway.search_items.call_args[0][0]
    assert query.item_type == "note"


def test_purge_attachments_batch_scan_failure_counts_errors_per_parent(scan_gateway):
    """A failed batched scan must still report one error per requested
    parent, matching the pre-batching per-item error-isolation behavior."""
    mock_gateway = scan_gateway
    purge_service = PurgeService(scan_gateway)
    mock_gateway.search_items.side_effect = Exception("API Error")

    stats = purge_service.purge_attachments(["P1", "P2", "P3"], dry_run=False)

    assert stats["errors"] == 3
    mock_gateway.get_item_children.assert_not_called()


def test_purge_attachments_stays_per_item_at_or_below_threshold(purge_service, mock_gateway):
    """A gateway that can't count (offline test double) keeps using
    per-parent get_item_children lookups rather than a full scan."""
    mock_gateway.get_item_children.return_value = [
        {"key": "A1", "data": {"itemType": "attachment", "version": 1}}
    ]
    mock_gateway.delete_item.return_value = True

    stats = purge_service.purge_attachments(["P1", "P2"], dry_run=False)

    assert stats["deleted"] == 2
    mock_gateway.search_items.assert_not_called()


def test_small_purge_in_a_large_library_looks_up_each_parent(scan_gateway):
    """Issue #441: purging 3 items paged through ~35k attachments (350
    pages) because the threshold was a fixed 2."""
    _CountingGateway.total = 35_000
    try:
        scan_gateway.get_item_children.return_value = [
            {"key": "A1", "data": {"itemType": "attachment", "version": 1}}
        ]
        scan_gateway.delete_item.return_value = True
        stats = PurgeService(scan_gateway).purge_attachments(["P1", "P2", "P3"], dry_run=False)
    finally:
        _CountingGateway.total = 150

    assert stats["deleted"] == 3
    scan_gateway.search_items.assert_not_called()
    assert scan_gateway.get_item_children.call_count == 3
    assert scan_gateway.counted == ["attachment"]


def test_purge_collection_assets_deletes_the_notes_of_every_item(purge_service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = "C1"
    items = [
        ZoteroItem(key="P1", version=1, item_type="journalArticle"),
        ZoteroItem(key="P2", version=1, item_type="journalArticle"),
    ]
    mock_gateway.get_items_in_collection.return_value = items
    mock_gateway.get_item_children.side_effect = lambda key: [
        {"key": f"N-{key}", "data": {"itemType": "note", "note": "plain text", "version": 3}}
    ]
    mock_gateway.delete_item.return_value = True

    stats = purge_service.purge_collection_assets("Col", types=["notes"], dry_run=False)

    assert stats["deleted"] == 2
    assert stats["errors"] == 0
    deleted = {call.args[0] for call in mock_gateway.delete_item.call_args_list}
    assert deleted == {"N-P1", "N-P2"}
