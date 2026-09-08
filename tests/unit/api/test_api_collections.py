"""
Issue #269: list_collections is an async def route that calls a
synchronous gateway method - see test_api_items.py for the full
rationale. This exercises the route end-to-end via TestClient, confirming
behavior is unchanged now that the call goes through run_in_threadpool.
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


def test_list_collections():
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "Root", "parentCollection": False}},
        {"key": "C2", "data": {"name": "Child", "parentCollection": "C1"}},
    ]

    response = client.get("/collections")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0] == {"key": "C1", "name": "Root", "parent": False}
    assert data[1] == {"key": "C2", "name": "Child", "parent": "C1"}
    mock_gateway.get_all_collections.assert_called_once()
