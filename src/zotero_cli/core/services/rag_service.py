from typing import Any, Dict, List

from zotero_cli.core.interfaces import (
    EmbeddingProvider,
    RAGService,
    VectorRepository,
    ZoteroGateway,
)
from zotero_cli.core.models import SearchResult, VectorChunk


class RAGServiceBase(RAGService):
    """
    Base implementation of the RAG Service.
    Handles ingestion of collections into a vector store and semantic querying.
    """

    def __init__(
        self,
        gateway: ZoteroGateway,
        vector_repo: VectorRepository,
        embedding_provider: EmbeddingProvider,
        attachment_service: Any,
    ):
        self.gateway = gateway
        self.vector_repo = vector_repo
        self.embedding_provider = embedding_provider
        self.attachment_service = attachment_service

    def ingest_collection(self, collection_key: str) -> Dict[str, Any]:
        """
        Ingest all items from a collection into the vector store.
        """
        col_id = self.gateway.get_collection_id_by_name(collection_key) or collection_key
        items = list(self.gateway.get_items_in_collection(col_id))

        processed = 0
        for item in items:
            # 1. Extract text from attachments (PDFs)
            text = self.attachment_service.get_fulltext(item.key)
            if not text:
                continue

            # 2. Chunk text (Simple split for now, ADR-RAG-001 will define strategy)
            chunks_text = self._chunk_text(text)

            # 3. Generate embeddings
            embeddings = self.embedding_provider.embed_batch(chunks_text)

            # 4. Store in vector repo
            vector_chunks = []
            for i, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings)):
                vector_chunks.append(
                    VectorChunk(
                        item_key=item.key, chunk_index=i, text=chunk_text, embedding=embedding
                    )
                )

            self.vector_repo.store_chunks(vector_chunks)
            processed += 1

        return {"processed": processed}

    def query(self, prompt: str, top_k: int = 5) -> List[SearchResult]:
        """
        Perform semantic search against the vector store.
        """
        embedding = self.embedding_provider.embed_text(prompt)
        return self.vector_repo.search(embedding, top_k=top_k)

    def get_context(self, item_key: str) -> str:
        """
        Retrieve all text chunks for a specific item to build LLM context.
        """
        chunks = self.vector_repo.get_chunks_by_item(item_key)
        return "\n\n".join([c.text for c in chunks])

    def _chunk_text(self, text: str, chunk_size: int = 1000) -> List[str]:
        """
        Primitive chunking strategy. To be replaced by recursive splitting.
        """
        if not text:
            return []
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
