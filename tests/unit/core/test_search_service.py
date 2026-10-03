"""The one search behind `search` and the MCP search tool (Issues #557, #560, #562)."""

from typing import List, Optional
from unittest.mock import create_autospec

import pytest

from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.interfaces import ItemSearch
from zotero_cli.core.services.search_service import SearchRequest, SearchService
from zotero_cli.core.zotero_item import ZoteroItem


def _item(key: str, date: Optional[str] = None, added: Optional[str] = None) -> ZoteroItem:
    return ZoteroItem(key=key, version=1, item_type="book", title=key, date=date, date_added=added)


def _keys(hits) -> List[str]:
    return [item.key for item, _ in hits]


def test_the_request_builds_the_server_side_query() -> None:
    query = SearchRequest(
        text="attention", tags=["a", "b"], item_type="book", collection_key="C1",
        sort="title", direction="asc",
    ).query()  # fmt: skip
    assert (query.q, query.tag, query.item_type, query.collection) == (
        "attention", ["a", "b"], "book", "C1",
    )  # fmt: skip
    assert (query.sort, query.direction) == ("title", "asc")


def test_without_sort_options_the_default_order_is_kept() -> None:
    query = SearchRequest(text="x").query()
    assert (query.sort, query.direction, query.tag) == ("date", "desc", None)


def test_full_text_requests_do_not_send_the_words_as_a_keyword() -> None:
    assert SearchRequest(text="words", fulltext=True).query().q is None


def test_a_keyword_search_pairs_each_item_with_no_score() -> None:
    backend = create_autospec(ItemSearch, instance=True)
    backend.search_items.return_value = [_item("A"), _item("B")]

    hits = list(SearchService(backend).search(SearchRequest(text="x")))

    assert [(i.key, score) for i, score in hits] == [("A", None), ("B", None)]


def test_a_full_text_search_keeps_the_scores_and_the_order() -> None:
    backend = create_autospec(ItemSearch, instance=True)
    backend.search_fulltext.return_value = [(_item("A"), 2.0), (_item("B"), 1.0)]

    hits = list(SearchService(backend).search(SearchRequest(text="words", fulltext=True)))

    assert [(i.key, s) for i, s in hits] == [("A", 2.0), ("B", 1.0)]
    assert backend.search_fulltext.call_args.args[0] == "words"


def test_full_text_needs_words() -> None:
    service = SearchService(create_autospec(ItemSearch, instance=True))
    request = SearchRequest(fulltext=True)
    with pytest.raises(UsageError, match="needs words"):
        service.search(request)


def test_a_negative_start_is_refused_before_any_request() -> None:
    backend = create_autospec(ItemSearch, instance=True)
    service = SearchService(backend)
    request = SearchRequest(text="x", start=-1)
    with pytest.raises(UsageError, match="--start"):
        service.search(request)
    backend.search_items.assert_not_called()


def test_year_and_date_added_filters_apply_as_results_arrive() -> None:
    backend = create_autospec(ItemSearch, instance=True)
    backend.search_items.return_value = [
        _item("OLD", "2010", "2026-01-01T00:00:00Z"),
        _item("IN", "2020", "2026-02-10T00:00:00Z"),
        _item("LATE", "2020", "2026-05-01T00:00:00Z"),
        _item("NODATE", None, "2026-02-10T00:00:00Z"),
    ]
    request = SearchRequest(
        text="x", years=(2018, 2022), added_since="2026-02-01", added_until="2026-03-01"
    )

    assert _keys(SearchService(backend).search(request)) == ["IN"]


def test_paging_counts_only_the_results_that_pass_the_filters() -> None:
    backend = create_autospec(ItemSearch, instance=True)
    backend.search_items.return_value = iter(
        [_item("A", "2020"), _item("B", "1999"), _item("C", "2021"), _item("D", "2022")]
    )

    hits = SearchService(backend).search(
        SearchRequest(text="x", years=(2020, None), start=1, limit=1)
    )

    assert _keys(hits) == ["C"]


@pytest.mark.parametrize(
    ("start", "limit", "expected"), [(0, 2, [0, 1]), (3, 0, [3, 4, 5]), (4, 10, [4, 5]), (9, 2, [])]
)
def test_window(start: int, limit: int, expected: List[int]) -> None:
    assert list(SearchService.window(iter(range(6)), start, limit)) == expected


def test_a_limit_stops_reading_early() -> None:
    pulled: List[int] = []

    def source():
        for n in range(1000):
            pulled.append(n)
            yield n

    assert list(SearchService.window(source(), 0, 3)) == [0, 1, 2]
    assert len(pulled) == 3
