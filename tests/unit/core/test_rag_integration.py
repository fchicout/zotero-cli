import pytest
import os
from unittest.mock import MagicMock
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.core.config import ZoteroConfig

@pytest.mark.unit
def test_rag_full_flow(tmp_path, monkeypatch):
    """
    Verifies the complete RAG flow: Ingest -> Query -> Context.
    Uses MockEmbeddingProvider and temp SQLite database.
    """
    # 1. Setup Mock Environment
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    
    mock_config = ZoteroConfig(
        api_key="fake_api_key",
        library_id="fake_lib_id",
        openai_api_key=None # This ensures MockEmbeddingProvider is used
    )
    
    # Mock config retrieval
    monkeypatch.setattr("zotero_cli.core.config.get_config", lambda: mock_config)
    monkeypatch.setattr("zotero_cli.core.config.get_config_path", lambda: config_file)
    
    # 2. Mock Infrastructure
    gateway = MagicMock()
    mock_item = MagicMock()
    mock_item.key = "KEY1"
    gateway.get_collection_id_by_name.return_value = "COL1"
    gateway.get_items_in_collection.return_value = [mock_item]
    
    # Ensure Factory returns our mock gateway
    monkeypatch.setattr(GatewayFactory, "get_zotero_gateway", lambda *args, **kwargs: gateway)
    
    # Mock AttachmentService.get_fulltext
    attachment_service = MagicMock()
    attachment_service.get_fulltext.return_value = "This is a test document about RAG."
    monkeypatch.setattr(GatewayFactory, "get_attachment_service", lambda *args, **kwargs: attachment_service)
    
    # 3. Execution
    service = GatewayFactory.get_rag_service()
    
    # A. Ingest
    stats = service.ingest_collection("Test")
    assert stats["processed"] == 1
    
    # B. Query
    results = service.query("test document")
    assert len(results) > 0
    assert results[0].item_key == "KEY1"
    assert "RAG" in results[0].text
    
    # C. Context
    context = service.get_context("KEY1")
    assert "test document" in context
    assert "RAG" in context

@pytest.mark.unit
def test_rag_persistence(tmp_path, monkeypatch):
    """
    Verifies that chunks are persisted in the SQLite database across service instances.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    
    mock_config = ZoteroConfig(api_key="f", library_id="f")
    monkeypatch.setattr("zotero_cli.core.config.get_config", lambda: mock_config)
    monkeypatch.setattr("zotero_cli.core.config.get_config_path", lambda: config_file)
    
    # Store something
    repo1 = GatewayFactory.get_vector_repository()
    from zotero_cli.core.models import VectorChunk
    repo1.store_chunks([VectorChunk(item_key="K1", chunk_index=0, text="hello", embedding=[1.0])])
    
    # Retrieve from a new instance
    repo2 = GatewayFactory.get_vector_repository()
    chunks = repo2.get_chunks_by_item("K1")
    assert len(chunks) == 1
    assert chunks[0].text == "hello"
