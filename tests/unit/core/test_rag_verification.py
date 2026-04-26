from unittest.mock import MagicMock

import pytest

from zotero_cli.core.models import SearchResult
from zotero_cli.core.services.rag_service import RAGServiceBase


@pytest.fixture
def mock_deps():
    gateway = MagicMock()
    vector_repo = MagicMock()
    embedding_provider = MagicMock()
    attachment_service = MagicMock()
    orchestrator = MagicMock()
    citation_service = MagicMock()
    return (
        gateway,
        vector_repo,
        embedding_provider,
        attachment_service,
        orchestrator,
        citation_service,
    )


def test_verify_results_success(mock_deps):
    (
        gateway,
        vector_repo,
        embedding_provider,
        attachment_service,
        orchestrator,
        citation_service,
    ) = mock_deps
    service = RAGServiceBase(
        gateway, vector_repo, embedding_provider, attachment_service, orchestrator, citation_service
    )

    # Setup result
    res = SearchResult(item_key="K1", text="text", score=0.9, metadata={})

    # Mock gateway item
    from zotero_cli.core.zotero_item import ZoteroItem

    mock_item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="Paper 1")
    mock_item.doi = "10.1/1"
    gateway.get_item.return_value = mock_item
    gateway.get_item_children.return_value = []
    citation_service.resolve_citation_key.return_value = "Key2024"

    verified = service.verify_results([res])

    assert len(verified) == 1
    assert verified[0].is_verified is True
    assert verified[0].citation_key == "Key2024"


def test_verify_results_missing_id(mock_deps):
    (
        gateway,
        vector_repo,
        embedding_provider,
        attachment_service,
        orchestrator,
        citation_service,
    ) = mock_deps
    service = RAGServiceBase(
        gateway, vector_repo, embedding_provider, attachment_service, orchestrator, citation_service
    )

    from zotero_cli.core.zotero_item import ZoteroItem

    mock_item = ZoteroItem(key="K2", version=1, item_type="journalArticle", title="Paper 2")
    mock_item.doi = None  # Missing ID
    gateway.get_item.return_value = mock_item
    gateway.get_item_children.return_value = []

    res = SearchResult(item_key="K2", text="text", score=0.9, metadata={})
    verified = service.verify_results([res])

    assert verified[0].is_verified is False
    assert "Missing DOI or arXiv ID" in verified[0].verification_errors
