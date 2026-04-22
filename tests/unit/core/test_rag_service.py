from unittest.mock import MagicMock

import pytest

from zotero_cli.core.interfaces import EmbeddingProvider, VectorRepository, ZoteroGateway
from zotero_cli.core.models import SearchResult
from zotero_cli.core.services.rag_service import RAGServiceBase


@pytest.fixture
def mock_deps():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()
    return gateway, vector_repo, embedding_provider, attachment_service

@pytest.mark.unit
def test_rag_ingest_intersection_logic(mock_deps):
    gateway, vector_repo, embedding_provider, attachment_service = mock_deps

    # 1. Setup Items: One approved but low QA, one approved and high QA
    item_low_qa = MagicMock()
    item_low_qa.key = "LOW_QA"
    item_low_qa.tags = ["rsl:include"]
    note_low = {"data": {"itemType": "note", "note": '{"action": "data_extraction", "quality_score": 0.3, "sdb_version": "1.2"}'}}

    item_high_qa = MagicMock()
    item_high_qa.key = "HIGH_QA"
    item_high_qa.tags = ["rsl:include"]
    note_high = {"data": {"itemType": "note", "note": '{"action": "data_extraction", "quality_score": 0.9, "sdb_version": "1.2"}'}}

    gateway.get_all_items.return_value = iter([item_low_qa, item_high_qa])
    gateway.get_item_children.side_effect = lambda k: [note_low] if k == "LOW_QA" else ([note_high] if k == "HIGH_QA" else [])

    attachment_service.get_fulltext.return_value = "text"
    embedding_provider.embed_batch.return_value = [[0.1]]

    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)

    # 2. Action: Ingest with BOTH approved=True AND min_qa=0.8
    result = service.ingest(approved_only=True, min_qa_score=0.8)

    # 3. Verify: Only HIGH_QA should be processed
    assert result["processed"] == 1
    assert result["skipped_low_qa"] == 1
    vector_repo.delete_chunks_by_item.assert_called_once_with("HIGH_QA")

@pytest.mark.unit
def test_rag_ingest_prune_logic(mock_deps):
    gateway, vector_repo, embedding_provider, attachment_service = mock_deps
    gateway.get_all_items.return_value = iter([])

    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)

    # Prune should call purge_all
    service.ingest(prune=True)
    vector_repo.purge_all.assert_called_once()

@pytest.mark.unit
def test_rag_query(mock_deps):
    gateway, vector_repo, embedding_provider, attachment_service = mock_deps
    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)

    mock_result = SearchResult(item_key="KEY1", text="Sample snippet", score=0.9, metadata={})
    vector_repo.search.return_value = [mock_result]
    embedding_provider.embed_text.return_value = [0.1, 0.2]

    # Mock gateway resolution
    mock_item = MagicMock()
    mock_item.key = "KEY1"
    mock_item.title = "Sample Paper"
    gateway.get_item.return_value = mock_item

    results = service.query("search query")

    assert len(results) == 1
    assert results[0].item_key == "KEY1"
    assert results[0].item.title == "Sample Paper"
    gateway.get_item.assert_called_once_with("KEY1")
