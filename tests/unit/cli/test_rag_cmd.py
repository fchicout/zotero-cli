import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.rag_cmd import RAGCommand
from zotero_cli.core.models import SearchResult
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_rag_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_rag_service") as mock:
        yield mock.return_value


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "fake_key")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "fake_id")


def test_rag_query_table_display(mock_rag_service, env_vars, capsys):
    # Mock search result with item
    mock_item = ZoteroItem(
        key="KEY1",
        version=1,
        item_type="journalArticle",
        title="Test Title",
        authors=["Author One", "Author Two"],
    )
    mock_result = SearchResult(
        item_key="KEY1", text="Short snippet", score=0.9876, metadata={"chunk": 0}, item=mock_item
    )
    mock_rag_service.query.return_value = [mock_result]

    args = argparse.Namespace(
        verb="query", prompt="test prompt", format="table", verify=False, user=False, top_k=5
    )
    # Force wide console to prevent truncation
    with patch("rich.console.Console.width", 200):
        RAGCommand().execute(args)

    out = capsys.readouterr().out
    assert "[1] KEY1" in out
    assert "Score: 0.9876" in out
    assert "Test Title" in out


def test_rag_query_verify_display(mock_rag_service, env_vars, capsys):
    from zotero_cli.core.models import ScreeningStatus, VerifiedSearchResult

    mock_item = ZoteroItem(
        key="KEY1",
        version=1,
        item_type="journalArticle",
        title="Verified Paper",
        authors=["John Doe"],
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
        citation_key="Doe2024",
    )
    mock_rag_service.query.return_value = [mock_result]
    mock_rag_service.verify_results.return_value = [mock_result]

    args = argparse.Namespace(
        verb="query", prompt="test", format="table", verify=True, user=False, top_k=5
    )
    RAGCommand().execute(args)

    out = capsys.readouterr().out
    assert "Verifying results..." in out
    assert "Verified Paper" in out


def test_rag_query_json_display(mock_rag_service, env_vars, capsys):
    # Mock search result with item
    mock_item = ZoteroItem(
        key="KEY1",
        version=1,
        item_type="journalArticle",
        title="Test Title",
        authors=["Author One"],
    )
    mock_result = SearchResult(
        item_key="KEY1",
        text="Full untruncated snippet text.",
        score=0.95,
        metadata={"chunk": 1},
        item=mock_item,
    )
    mock_rag_service.query.return_value = [mock_result]

    args = argparse.Namespace(
        verb="query", prompt="test prompt", format="json", verify=False, user=False, top_k=5
    )
    RAGCommand().execute(args)

    out = capsys.readouterr().out
    assert '"item_key": "KEY1"' in out
    assert '"text": "Full untruncated snippet text."' in out


def test_rag_purge_item(mock_rag_service, env_vars, capsys):
    args = argparse.Namespace(verb="purge", key="ITEM123", collection=None, user=False, all=False)
    RAGCommand().execute(args)

    mock_rag_service.purge.assert_called_once_with(item_key="ITEM123")


def test_rag_query_no_results_json(mock_rag_service, env_vars, capsys):
    mock_rag_service.query.return_value = []

    args = argparse.Namespace(
        verb="query", prompt="no results", format="json", verify=False, user=False, top_k=5
    )
    RAGCommand().execute(args)

    out = capsys.readouterr().out
    assert out.strip() == "[]"


def test_rag_ingest_collection(mock_rag_service, env_vars, capsys):
    mock_rag_service.ingest.return_value = {"processed": 3, "skipped_low_qa": 0}

    args = argparse.Namespace(
        verb="ingest",
        target=None,
        tree=None,
        collection="COL123",
        key=None,
        approved=True,
        prune=True,
        qa_limit=0.8,
        user=False,
    )
    RAGCommand().execute(args)

    mock_rag_service.ingest.assert_called_once()
    out = capsys.readouterr().out
    assert "Ingestion complete" in out
    assert "Processed: 3 items" in out


def test_rag_ingest_invalid_params(mock_rag_service, env_vars, capsys):
    # qa-approved with collection
    args = argparse.Namespace(
        verb="ingest",
        target="qa-approved",
        tree=None,
        collection="COL123",
        key=None,
        approved=False,
        prune=False,
        qa_limit=None,
        user=False,
    )
    RAGCommand().execute(args)
    out = capsys.readouterr().out
    assert "Cannot specify --collection or --key with 'qa-approved' target" in out

    # tree without qa-approved
    args2 = argparse.Namespace(
        verb="ingest",
        target=None,
        tree="tree_name",
        collection=None,
        key=None,
        approved=False,
        prune=False,
        qa_limit=None,
        user=False,
    )
    RAGCommand().execute(args2)
    out2 = capsys.readouterr().out
    assert "Cannot specify --tree without 'qa-approved' target" in out2


def test_rag_context_success(mock_rag_service, env_vars, capsys):
    mock_rag_service.get_context.return_value = "This is full paper context"
    args = argparse.Namespace(verb="context", key="KEY123", user=False)
    RAGCommand().execute(args)
    out = capsys.readouterr().out
    assert "This is full paper context" in out


def test_rag_context_empty(mock_rag_service, env_vars, capsys):
    mock_rag_service.get_context.return_value = None
    args = argparse.Namespace(verb="context", key="KEY123", user=False)
    RAGCommand().execute(args)
    out = capsys.readouterr().out
    assert "No context found for this item" in out


def test_rag_purge_all_and_col(mock_rag_service, env_vars):
    args_all = argparse.Namespace(verb="purge", all=True, key=None, collection=None, user=False)
    RAGCommand().execute(args_all)
    mock_rag_service.purge.assert_called_with(purge_all=True)

    args_col = argparse.Namespace(
        verb="purge", all=False, key=None, collection="COL_KEY", user=False
    )
    RAGCommand().execute(args_col)
    mock_rag_service.purge.assert_called_with(collection_key="COL_KEY")


@patch("huggingface_hub.scan_cache_dir")
@patch("shutil.rmtree")
@patch("rich.prompt.Confirm.ask", return_value=True)
def test_rag_model_clean(mock_confirm, mock_rmtree, mock_scan, env_vars, capsys):
    mock_repo = MagicMock()
    mock_repo.repo_path = "/path/to/repo"
    mock_scan.return_value.size_on_disk_str = "1.5GB"
    mock_scan.return_value.repos = [mock_repo]

    args = argparse.Namespace(verb="model", model_verb="clean", user=False)
    RAGCommand().execute(args)

    out = capsys.readouterr().out
    assert "Model Cleanup Utility" in out
    assert "HF cache usage: 1.5GB" in out
    mock_rmtree.assert_called()


@patch("rich.prompt.Prompt.ask", side_effect=["1", "3", "y"])
@patch("huggingface_hub.snapshot_download")
def test_rag_model_set(mock_download, mock_prompt, env_vars, capsys):
    args = argparse.Namespace(verb="model", model_verb="set", user=False)
    RAGCommand().execute(args)

    out = capsys.readouterr().out
    assert "Embedding Models" in out
    assert "Generative Models" in out
    assert "Configuration updated" in out
    mock_download.assert_called_once()


def test_rag_register_args():
    parser = argparse.ArgumentParser()
    RAGCommand().register_args(parser)
    # verify main subparsers are added
    actions = parser._actions
    assert len(actions) > 0
