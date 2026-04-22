import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main


@pytest.fixture
def mock_rag_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_rag_service") as mock_get:
        yield mock_get.return_value

@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")

def test_rag_ingest_key(mock_rag_service, env_vars, capsys):
    mock_rag_service.ingest.return_value = {"processed": 1}

    test_args = ["zotero-cli", "rag", "ingest", "--key", "ITEM123"]
    with patch.object(sys, "argv", test_args):
        main()

    mock_rag_service.ingest.assert_called_once()
    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["item_key"] == "ITEM123"
    assert kwargs["collection_key"] is None

    out = capsys.readouterr().out
    assert "Streaming ingestion from item 'ITEM123'..." in out
    assert "Processed: 1 items" in out

def test_rag_ingest_approved(mock_rag_service, env_vars, capsys):
    mock_rag_service.ingest.return_value = {"processed": 5, "skipped_not_approved": 2}

    test_args = ["zotero-cli", "rag", "ingest", "--approved"]

    with patch.object(sys, "argv", test_args):
        main()

    mock_rag_service.ingest.assert_called_once()
    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["approved_only"] is True

    out = capsys.readouterr().out
    assert "Streaming ingestion from entire library + approved items..." in out
    assert "Processed: 5 items" in out
    assert "Skipped (Not Approved): 2" in out

def test_rag_ingest_qa_limit(mock_rag_service, env_vars, capsys):
    mock_rag_service.ingest.return_value = {"processed": 3, "skipped_low_qa": 4}

    test_args = ["zotero-cli", "rag", "ingest", "--collection", "MyColl", "--qa-limit", "0.8"]
    with patch.object(sys, "argv", test_args):
        main()

    mock_rag_service.ingest.assert_called_once()
    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["collection_key"] == "MyColl"
    assert kwargs["min_qa_score"] == 0.8

    out = capsys.readouterr().out
    assert "Streaming ingestion from collection 'MyColl' + QA limit >= 0.8..." in out
    assert "Processed: 3 items" in out
    assert "Skipped (Low QA Score): 4" in out

def test_rag_ingest_prune(mock_rag_service, env_vars, capsys):
    mock_rag_service.ingest.return_value = {"processed": 1}

    test_args = ["zotero-cli", "rag", "ingest", "--key", "K1", "--prune"]
    with patch.object(sys, "argv", test_args):
        main()

    mock_rag_service.ingest.assert_called_once()
    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["prune"] is True

def test_rag_ingest_mutually_exclusive(mock_rag_service, env_vars, capsys):
    # This should fail at the argparse level
    test_args = ["zotero-cli", "rag", "ingest", "--collection", "Col", "--key", "Key"]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit):
            main()
