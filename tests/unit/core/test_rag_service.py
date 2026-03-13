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

    results = service.query("search query")

    assert len(results) == 1
    assert results[0].item_key == "KEY1"
