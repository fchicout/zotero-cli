"""
Issue #256: RAGServiceBase.ingest() mixed item-selection, tag/QA
filtering, and concurrency orchestration in one method. These tests
exercise the extracted RAGIngestItemSelector in isolation - the whole
point of the refactor was to make each selection/filter concern
independently testable without spinning up the full ingest() pipeline.
"""

from unittest.mock import MagicMock

from zotero_cli.core.services.rag_service import RAGIngestItemSelector


def _make_item(key, tags=None):
    item = MagicMock()
    item.key = key
    item.tags = tags or []
    return item


def test_resolve_defaults_to_full_library():
    gateway = MagicMock()
    orchestrator = MagicMock()
    items = [_make_item("A"), _make_item("B")]
    gateway.get_all_items.return_value = items

    selector = RAGIngestItemSelector(gateway, orchestrator)
    result, skipped_low_qa = selector.resolve()

    assert result == items
    assert skipped_low_qa == 0
    gateway.get_all_items.assert_called_once()


def test_resolve_by_single_item_key():
    gateway = MagicMock()
    orchestrator = MagicMock()
    item = _make_item("K1")
    gateway.get_item.return_value = item

    selector = RAGIngestItemSelector(gateway, orchestrator)
    result, _ = selector.resolve(item_key="K1")

    assert result == [item]
    gateway.get_item.assert_called_once_with("K1")


def test_resolve_by_collection_key():
    gateway = MagicMock()
    orchestrator = MagicMock()
    items = [_make_item("A")]
    gateway.get_collection_id_by_name.return_value = "COL_ID"
    gateway.get_items_in_collection.return_value = items

    selector = RAGIngestItemSelector(gateway, orchestrator)
    result, _ = selector.resolve(collection_key="My Collection")

    assert result == items
    gateway.get_items_in_collection.assert_called_once_with("COL_ID")


def test_resolve_approved_only_filters_by_screening_tag():
    gateway = MagicMock()
    orchestrator = MagicMock()
    included = _make_item("IN", tags=["rsl:include"])
    excluded = _make_item("OUT", tags=["rsl:exclude"])
    gateway.get_all_items.return_value = [included, excluded]

    selector = RAGIngestItemSelector(gateway, orchestrator)
    result, _ = selector.resolve(approved_only=True)

    assert result == [included]


def test_resolve_min_qa_score_filters_and_counts_skipped():
    gateway = MagicMock()
    orchestrator = MagicMock()
    high_qa = _make_item("HIGH")
    low_qa = _make_item("LOW")
    gateway.get_all_items.return_value = [high_qa, low_qa]

    def get_item_children(key):
        if key == "HIGH":
            note = '{"action": "data_extraction", "quality_score": 0.9, "sdb_version": "1.2"}'
        else:
            note = '{"action": "data_extraction", "quality_score": 0.1, "sdb_version": "1.2"}'
        return [{"data": {"itemType": "note", "note": note}}]

    gateway.get_item_children.side_effect = get_item_children

    selector = RAGIngestItemSelector(gateway, orchestrator)
    result, skipped_low_qa = selector.resolve(min_qa_score=0.5)

    assert result == [high_qa]
    assert skipped_low_qa == 1


def test_get_item_max_qa_score_returns_negative_one_when_no_qa_note():
    gateway = MagicMock()
    orchestrator = MagicMock()
    gateway.get_item_children.return_value = []

    selector = RAGIngestItemSelector(gateway, orchestrator)
    assert selector.get_item_max_qa_score(_make_item("K1")) == -1.0
