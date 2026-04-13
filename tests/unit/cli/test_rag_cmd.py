import sys
import json
from unittest.mock import patch, MagicMock

import pytest

from zotero_cli.cli.main import main
from zotero_cli.core.models import SearchResult
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_rag_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_rag_service") as mock_get:
        yield mock_get.return_value


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")


def test_rag_query_table_display(mock_rag_service, env_vars, capsys):
    # Mock search result with item
    mock_item = ZoteroItem(
        key="KEY1",
        version=1,
        item_type="journalArticle",
        title="Test Title",
        authors=["Author One", "Author Two"]
    )
    mock_result = SearchResult(
        item_key="KEY1",
        text="This is the snippet text that should appear.",
        score=0.9876,
        metadata={"chunk": 0},
        item=mock_item
    )
    mock_rag_service.query.return_value = [mock_result]

    test_args = ["zotero-cli", "rag", "query", "test prompt"]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "Querying vector store for: 'test prompt'" in out
    assert "Test Title" in out
    assert "Author One Author Two" in out or "Author One, Author Two" in out
    assert "0.9876" in out
    assert "This is the snippet text" in out


def test_rag_query_json_display(mock_rag_service, env_vars, capsys):
    # Mock search result with item
    mock_item = ZoteroItem(
        key="KEY1",
        version=1,
        item_type="journalArticle",
        title="Test Title",
        authors=["Author One"]
    )
    mock_result = SearchResult(
        item_key="KEY1",
        text="Full untruncated snippet text.",
        score=0.95,
        metadata={"chunk": 1},
        item=mock_item
    )
    mock_rag_service.query.return_value = [mock_result]

    test_args = ["zotero-cli", "rag", "query", "test prompt", "--json"]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    # Parse JSON output
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["item_key"] == "KEY1"
    assert data[0]["text"] == "Full untruncated snippet text."
    assert data[0]["score"] == 0.95
    assert data[0]["item"]["title"] == "Test Title"


def test_rag_query_no_results(mock_rag_service, env_vars, capsys):
    mock_rag_service.query.return_value = []

    test_args = ["zotero-cli", "rag", "query", "no results"]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "No relevant snippets found." in out


def test_rag_query_no_results_json(mock_rag_service, env_vars, capsys):
    mock_rag_service.query.return_value = []

    test_args = ["zotero-cli", "rag", "query", "no results", "--json"]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data == []
