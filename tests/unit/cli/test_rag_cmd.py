import json
import sys
from unittest.mock import patch

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
        text="Short snippet",
        score=0.9876,
        metadata={"chunk": 0},
        item=mock_item
    )
    mock_rag_service.query.return_value = [mock_result]

    test_args = ["zotero-cli", "rag", "query", "test prompt"]
    # Force wide console to prevent truncation
    with patch("rich.console.Console.width", 200):
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Querying vector store for: 'test prompt'" in out
    assert "Test Title" in out
    assert "Author One" in out
    assert "0.9876" in out
    assert "Short snippet" in out
    # New column
    assert "Verified" in out
    assert "N/A" in out


def test_rag_query_verify_display(mock_rag_service, env_vars, capsys):
    from zotero_cli.core.models import ScreeningStatus, VerifiedSearchResult

    mock_item = ZoteroItem(
        key="KEY1",
        version=1,
        item_type="journalArticle",
        title="Verified Paper",
        authors=["John Doe"]
    )
    mock_result = VerifiedSearchResult(
        item_key="KEY1",
        text="Snippet text.",
        score=0.9,
        metadata={},
        item=mock_item,
        is_verified=True,
        verification_errors=[],
        screening_status=ScreeningStatus.ACCEPTED,
        citation_key="Doe2024"
    )
    mock_rag_service.query.return_value = [mock_result]
    mock_rag_service.verify_results.return_value = [mock_result]

    test_args = ["zotero-cli", "rag", "query", "test", "--verify"]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "Verifying results..." in out
    assert "Verified Paper" in out
    assert "Yes" in out


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
