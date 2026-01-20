from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from zotero_cli.api.dependencies import get_gateway
from zotero_cli.api.main import create_app
from zotero_cli.core.zotero_item import ZoteroItem

# Mock Gateway
mock_gateway = MagicMock()


def override_get_gateway():
    return mock_gateway


app = create_app()
app.dependency_overrides[get_gateway] = override_get_gateway
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_mocks():
    mock_gateway.reset_mock()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_items():
    # Setup Mock
    item1 = ZoteroItem(key="ABC12345", version=1, item_type="journalArticle", raw_data={})
    item2 = ZoteroItem(key="DEF67890", version=1, item_type="report", raw_data={})
    mock_gateway.search_items.return_value = iter([item1, item2])

    # Execute
    response = client.get("/items")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["key"] == "ABC12345"


def test_get_item_detail():
    # Setup Mock
    item = ZoteroItem(
        key="ABC12345", version=1, item_type="journalArticle", raw_data={"title": "Test Paper"}
    )
    mock_gateway.get_item.return_value = item

    # Execute
    response = client.get("/items/ABC12345")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "ABC12345"
    mock_gateway.get_item.assert_called_with("ABC12345")


def test_get_item_not_found():
    mock_gateway.get_item.return_value = None
    response = client.get("/items/MISSING")
    assert response.status_code == 404


def test_list_collections():
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "name": "Collection A"},
        {"key": "C2", "name": "Collection B"},
    ]

    response = client.get("/collections")
    assert response.status_code == 200
    assert len(response.json()) == 2
