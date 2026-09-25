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
    client = _client(FakeSession(_collections(250), fail_at_start=100))

    assert client.get_all_collections() == []


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
