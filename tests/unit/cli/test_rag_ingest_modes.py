import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main


@pytest.fixture
def mock_rag_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_rag_service") as mock:
        yield mock.return_value


@pytest.fixture
def mock_gateway():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock:
        yield mock.return_value


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "fake_key")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "fake_id")


def test_rag_ingest_key(mock_rag_service, mock_gateway, env_vars):
    mock_rag_service.ingest.return_value = {"processed": 1}

    test_args = ["zotero-cli", "rag", "ingest", "--key", "ITEM123"]
    with patch.object(sys, "argv", test_args):
        main()

    mock_rag_service.ingest.assert_called_once()
    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["item_key"] == "ITEM123"


def test_rag_ingest_approved(mock_rag_service, mock_gateway, env_vars):
    mock_rag_service.ingest.return_value = {"processed": 5, "skipped_not_approved": 2}

    test_args = ["zotero-cli", "rag", "ingest", "--approved"]

    with patch.object(sys, "argv", test_args):
        main()

    mock_rag_service.ingest.assert_called_once()
    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["approved_only"] is True


def test_rag_ingest_qa_limit(mock_rag_service, mock_gateway, env_vars):
    mock_rag_service.ingest.return_value = {"processed": 3, "skipped_low_qa": 4}

    test_args = ["zotero-cli", "rag", "ingest", "--collection", "MyColl", "--qa-limit", "0.8"]
    with patch.object(sys, "argv", test_args):
        main()

    mock_rag_service.ingest.assert_called_once()
    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["collection_key"] == "MyColl"
    assert kwargs["min_qa_score"] == 0.8


def test_rag_ingest_prune(mock_rag_service, mock_gateway, env_vars):
    mock_rag_service.ingest.return_value = {"processed": 1}

    test_args = ["zotero-cli", "rag", "ingest", "--prune"]
    with patch.object(sys, "argv", test_args):
        main()

    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["prune"] is True


def test_rag_ingest_no_prune(mock_rag_service, mock_gateway, env_vars):
    mock_rag_service.ingest.return_value = {"processed": 1}

    test_args = ["zotero-cli", "rag", "ingest", "--no-prune"]
    with patch.object(sys, "argv", test_args):
        main()

    kwargs = mock_rag_service.ingest.call_args.kwargs
    assert kwargs["prune"] is False
