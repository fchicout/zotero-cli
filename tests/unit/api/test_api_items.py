"""
Issue #269: list_items/get_item are async def routes that call synchronous
gateway methods - unless offloaded to the threadpool, FastAPI runs them
directly on the event loop, blocking every concurrent client for the
duration of the call. These tests exercise the routes end-to-end via
TestClient (which itself runs on a real event loop), confirming behavior
is unchanged now that the calls go through run_in_threadpool.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from zotero_cli.api.dependencies import get_gateway
from zotero_cli.api.main import create_app

mock_gateway = MagicMock()


def override_get_gateway():
    return mock_gateway


app = create_app()
app.dependency_overrides[get_gateway] = override_get_gateway
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_mocks():
    mock_gateway.reset_mock()


def _make_item(key: str, title: str):
    item = MagicMock()
    item.key = key
    item.title = title
    item.authors = ["Someone"]
    item.date = "2024"
    item.item_type = "journalArticle"
    item.has_pdf = False
    item.abstract = "An abstract"
    item.url = "http://example.com"
    item.doi = "10.1/x"
    item.raw_data = {}
    return item


def test_list_items():
    items = [_make_item("K1", "Paper One"), _make_item("K2", "Paper Two")]
    mock_gateway.search_items.return_value = iter(items)

    response = client.get("/items")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["key"] == "K1"
    assert data[0]["title"] == "Paper One"


def test_list_items_respects_limit():
    items = [_make_item(f"K{i}", f"Paper {i}") for i in range(5)]
    mock_gateway.search_items.return_value = iter(items)

    response = client.get("/items", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_item_found():
    mock_gateway.get_item.return_value = _make_item("K1", "Paper One")

    response = client.get("/items/K1")

    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "K1"
    assert data["title"] == "Paper One"
    mock_gateway.get_item.assert_called_once_with("K1")


def test_get_item_not_found():
    mock_gateway.get_item.return_value = None

    response = client.get("/items/MISSING")

    assert response.status_code == 404
