from unittest.mock import MagicMock

import pytest

from zotero_cli.core.interfaces import EmbeddingProvider, VectorRepository, ZoteroGateway
from zotero_cli.core.models import SearchResult
from zotero_cli.core.services.rag_service import RAGServiceBase


@pytest.mark.unit
def test_rag_ingest_collection():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()

    # Mock items in collection
    mock_item = MagicMock()
    mock_item.key = "KEY1"
    gateway.get_collection_id_by_name.return_value = "COL1"
    gateway.get_items_in_collection.return_value = [mock_item]

    # Mock PDF extraction
    attachment_service.get_fulltext.return_value = "This is a sample paper text."

    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)

    # Mock embedding
    embedding_provider.embed_batch.return_value = [[0.1, 0.2]]

    result = service.ingest_collection("Test Collection")

    assert result["processed"] == 1
    assert vector_repo.store_chunks.called


@pytest.mark.unit
def test_rag_query():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()

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
    assert results[0].item is not None
    assert results[0].item.title == "Sample Paper"
    gateway.get_item.assert_called_once_with("KEY1")


@pytest.mark.unit
def test_rag_ingest_idempotency():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()

    mock_item = MagicMock()
    mock_item.key = "KEY1"
    gateway.get_collection_id_by_name.return_value = "COL1"
    gateway.get_items_in_collection.return_value = [mock_item]
    attachment_service.get_fulltext.return_value = "text"
    embedding_provider.embed_batch.return_value = [[0.1]]

    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)

    service.ingest_collection("COL1")

    # Verify that delete_chunks_by_item was called before store_chunks
    vector_repo.delete_chunks_by_item.assert_called_once_with("KEY1")
    assert vector_repo.store_chunks.called


@pytest.mark.unit
def test_rag_purge():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()

    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)

    # Purge All
    service.purge(purge_all=True)
    vector_repo.purge_all.assert_called_once()

    # Purge Item
    service.purge(item_key="KEY1")
    vector_repo.delete_chunks_by_item.assert_called_with("KEY1")

    # Purge Collection
    mock_item = MagicMock()
    mock_item.key = "COL_ITEM_1"
    gateway.get_items_in_collection.return_value = [mock_item]
    service.purge(collection_key="COL1")
    vector_repo.delete_chunks_by_item.assert_called_with("COL_ITEM_1")


@pytest.mark.unit
def test_rag_ingest_item():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()

    mock_item = MagicMock()
    mock_item.key = "ITEM1"
    gateway.get_item.return_value = mock_item
    attachment_service.get_fulltext.return_value = "text"
    embedding_provider.embed_batch.return_value = [[0.1]]

    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)
    result = service.ingest_item("ITEM1")

    assert result["processed"] == 1
    vector_repo.delete_chunks_by_item.assert_called_with("ITEM1")


@pytest.mark.unit
def test_rag_ingest_approved():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()

    item1 = MagicMock()
    item1.key = "APPROVED_TAG"
    item1.tags = ["rsl:include"]

    item2 = MagicMock()
    item2.key = "APPROVED_NOTE"
    item2.tags = []
    
    # Mock note for item2
    note_item = {"data": {"itemType": "note", "note": '{"action": "screening_decision", "decision": "accepted"}'}}
    gateway.get_item_children.side_effect = lambda k: [note_item] if k == "APPROVED_NOTE" else []

    item3 = MagicMock()
    item3.key = "REJECTED"
    item3.tags = []

    gateway.get_all_items.return_value = [item1, item2, item3]
    attachment_service.get_fulltext.return_value = "text"
    embedding_provider.embed_batch.return_value = [[0.1]]

    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)
    result = service.ingest_approved()

    assert result["processed"] == 2
    assert result["skipped_not_approved"] == 1
    vector_repo.delete_chunks_by_item.assert_any_call("APPROVED_TAG")
    vector_repo.delete_chunks_by_item.assert_any_call("APPROVED_NOTE")


@pytest.mark.unit
def test_rag_ingest_by_qa_score():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()

    item1 = MagicMock()
    item1.key = "HIGH_QA"
    note1 = {"data": {"itemType": "note", "note": '{"action": "data_extraction", "quality_score": 0.9, "sdb_version": "1.2"}'}}

    item2 = MagicMock()
    item2.key = "LOW_QA"
    note2 = {"data": {"itemType": "note", "note": '{"action": "data_extraction", "quality_score": 0.5, "sdb_version": "1.2"}'}}

    gateway.get_all_items.return_value = [item1, item2]
    gateway.get_item_children.side_effect = lambda k: [note1] if k == "HIGH_QA" else ([note2] if k == "LOW_QA" else [])
    
    attachment_service.get_fulltext.return_value = "text"
    embedding_provider.embed_batch.return_value = [[0.1]]

    service = RAGServiceBase(gateway, vector_repo, embedding_provider, attachment_service)
    result = service.ingest_by_qa_score(0.8)

    assert result["processed"] == 1
    assert result["skipped_low_qa"] == 1
    vector_repo.delete_chunks_by_item.assert_called_with("HIGH_QA")
