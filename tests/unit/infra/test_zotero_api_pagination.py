"""Issue #394: collections, tags, children and groups were read with a single
request, so online listings stopped at 100 collections/tags and 25 children."""

from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import pytest
import requests

from zotero_cli.infra.zotero_api import ZoteroAPIClient


class FakeSession:
    """Serves `objects` in pages the way the Web API does: honours `start`
    and `limit` (capped at 100) and sends `Total-Results` unless told not to."""

    def __init__(
        self,
        objects: List[Dict[str, Any]],
        send_total: bool = True,
        fail_at_start: Optional[int] = None,
    ):
        self.objects = objects
        self.send_total = send_total
        self.fail_at_start = fail_at_start
        self.headers: Dict[str, str] = {}
        self.requests: List[Dict[str, Any]] = []

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Mock:
        params = params or {}
        self.requests.append({"url": url, **params})
        start = int(params.get("start", 0))
        if self.fail_at_start is not None and start >= self.fail_at_start:
            error = requests.exceptions.HTTPError("403 Forbidden")
            error.response = Mock(status_code=403)
            raise error
        # The API's default page size is 25 when no limit is sent.
        limit = min(int(params.get("limit", 25)), 100)
        response = Mock()
        response.json.return_value = self.objects[start : start + limit]
        response.headers = {"Total-Results": str(len(self.objects))} if self.send_total else {}
        response.raise_for_status.return_value = None
        return response


def _client(session: FakeSession) -> ZoteroAPIClient:
    client = ZoteroAPIClient("key", "123", "user")
    client.http.session = session  # type: ignore[assignment]
    return client


def _collections(n: int) -> List[Dict[str, Any]]:
    return [{"key": f"C{i:05d}", "data": {"name": f"Col {i}"}} for i in range(n)]


def test_get_all_collections_reads_every_page():
    session = FakeSession(_collections(250))
    client = _client(session)

    collections = client.get_all_collections()

    assert [c["key"] for c in collections] == [f"C{i:05d}" for i in range(250)]
    assert [r["start"] for r in session.requests] == [0, 100, 200]


def test_pagination_without_total_results_stops_on_a_short_page():
    session = FakeSession(_collections(250), send_total=False)

    assert len(_client(session).get_all_collections()) == 250
    assert len(session.requests) == 3


def test_exact_multiple_of_the_page_size_needs_no_extra_request_with_total():
    session = FakeSession(_collections(200))

    assert len(_client(session).get_all_collections()) == 200
    assert len(session.requests) == 2


def test_collection_name_past_the_first_page_resolves():
    client = _client(FakeSession(_collections(250)))

    assert client.get_collection_id_by_name("Col 240") == "C00240"


def test_get_item_children_reads_past_the_default_25():
    children = [{"key": f"N{i}", "data": {"itemType": "note"}} for i in range(30)]

    assert len(_client(FakeSession(children)).get_item_children("PARENT")) == 30


def test_get_tags_reads_every_page():
    tags = [{"tag": f"t{i}"} for i in range(150)]

    assert _client(FakeSession(tags)).get_tags() == [f"t{i}" for i in range(150)]


def test_get_user_groups_reads_every_page():
    groups = [{"id": i} for i in range(120)]

    assert len(_client(FakeSession(groups)).get_user_groups("123")) == 120


def test_an_error_on_a_later_page_never_yields_a_partial_collection_list():
    """A truncated list would make names past the cut look missing, so
    commands would create duplicates or report 'not found'."""
    from zotero_cli.core.exceptions import AuthError

    client = _client(FakeSession(_collections(250), fail_at_start=100))

    # An error, never a partial list (and since #369, never an empty one).
    with pytest.raises(AuthError):
        client.get_all_collections()


def test_paginate_raises_on_a_non_list_page():
    session = FakeSession([])
    response = Mock()
    response.json.return_value = {"error": "unexpected"}
    response.headers = {}
    session.get = Mock(return_value=response)  # type: ignore[method-assign]

    with pytest.raises(ValueError):
        list(_client(session)._paginate("collections"))


def test_items_are_paginated_with_the_same_paginator():
    items = [{"key": f"I{i}", "version": 1, "data": {"itemType": "book"}} for i in range(130)]

    keys = [item.key for item in _client(FakeSession(items)).get_all_items()]

    assert keys == [f"I{i}" for i in range(130)]


# ---- Issue #562: search filters reach the Web API ----------------------------------------


def test_a_search_in_a_collection_uses_that_collections_endpoint() -> None:
    from zotero_cli.core.models import ZoteroQuery

    session = FakeSession([{"key": "I1", "data": {"title": "T", "itemType": "book"}}])
    client = _client(session)

    keys = [i.key for i in client.search_items(ZoteroQuery(collection="COL1", tag="a"))]

    assert keys == ["I1"]
    assert session.requests[0]["url"].endswith("collections/COL1/items")
    assert session.requests[0]["tag"] == "a"


def test_a_search_without_a_collection_uses_the_items_endpoint() -> None:
    from zotero_cli.core.models import ZoteroQuery

    session = FakeSession([])
    list(_client(session).search_items(ZoteroQuery(q="x")))
    assert session.requests[0]["url"].endswith("/items") or session.requests[0]["url"] == "items"
    assert "collections" not in session.requests[0]["url"]


def test_several_tags_are_sent_as_repeated_parameters_and_sort_is_forwarded() -> None:
    from zotero_cli.core.models import ZoteroQuery

    session = FakeSession([])
    query = ZoteroQuery(
        tag=["to-read", "-archived"], item_type="book", sort="title", direction="asc"
    )
    list(_client(session).search_items(query))

    sent = session.requests[0]
    assert sent["tag"] == ["to-read", "-archived"]
    assert (sent["itemType"], sent["sort"], sent["direction"]) == ("book", "title", "asc")


def test_the_result_count_follows_the_collection_too() -> None:
    from zotero_cli.core.models import ZoteroQuery

    session = FakeSession([{"key": "I1", "data": {}}, {"key": "I2", "data": {}}])
    count = _client(session).count_search_results(ZoteroQuery(collection="COL1"))

    assert count == 2
    assert session.requests[0]["url"].endswith("collections/COL1/items")
