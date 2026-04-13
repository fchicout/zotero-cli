import json
import logging
from typing import Any, Callable, Dict, List, Optional

from zotero_cli.core.interfaces import (
    EmbeddingProvider,
    RAGService,
    VectorRepository,
    ZoteroGateway,
)
from zotero_cli.core.models import SearchResult, VectorChunk
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.core.utils.sdb_parser import parse_sdb_note

logger = logging.getLogger(__name__)


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

    def ingest_collection(
        self,
        collection_key: str,
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest all items from a collection into the vector store.
        """
        col_id = self.gateway.get_collection_id_by_name(collection_key) or collection_key
        items = list(self.gateway.get_items_in_collection(col_id))
        return self._ingest_items(items, on_item_processed)

    def ingest_item(
        self, item_key: str, on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a single item into the vector store.
        """
        item = self.gateway.get_item(item_key)
        if not item:
            return {"processed": 0, "error": f"Item {item_key} not found"}
        return self._ingest_items([item], on_item_processed)

    def ingest_approved(
        self, on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ) -> Dict[str, Any]:
        """
        Ingest all items with 'rsl:include' tag or accepted screening note.
        """
        all_items = list(self.gateway.get_all_items())
        approved_items = []
        skipped_count = 0

        for item in all_items:
            is_approved = False
            # Check Tags
            if "rsl:include" in item.tags:
                is_approved = True
            else:
                # Check Notes
                children = self.gateway.get_item_children(item.key)
                for child_raw in children:
                    # NoteRepo/Gateway might return raw dicts or objects depending on implementation
                    # We'll use get to be safe
                    if child_raw.get("data", {}).get("itemType") == "note":
                        note_content = child_raw.get("data", {}).get("note", "")
                        parsed = parse_sdb_note(note_content)
                        if parsed and parsed.get("action") == "screening_decision" and parsed.get("decision") == "accepted":
                            is_approved = True
                            break
            
            if is_approved:
                approved_items.append(item)
            else:
                skipped_count += 1

        res = self._ingest_items(approved_items, on_item_processed)
        res["skipped_not_approved"] = skipped_count
        return res

    def ingest_by_qa_score(
        self, min_score: float, on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ) -> Dict[str, Any]:
        """
        Ingest items with extraction QA score >= min_score.
        """
        all_items = list(self.gateway.get_all_items())
        qualified_items = []
        skipped_count = 0

        for item in all_items:
            max_score = -1.0
            children = self.gateway.get_item_children(item.key)
            for child_raw in children:
                if child_raw.get("data", {}).get("itemType") == "note":
                    note_content = child_raw.get("data", {}).get("note", "")
                    parsed = parse_sdb_note(note_content)
                    if parsed and parsed.get("action") == "data_extraction":
                        # Check for quality_score in data or top-level
                        score = parsed.get("quality_score") or parsed.get("data", {}).get("quality_score")
                        if score is not None:
                            try:
                                f_score = float(score)
                                if f_score > max_score:
                                    max_score = f_score
                            except (ValueError, TypeError):
                                continue
            
            if max_score >= min_score:
                qualified_items.append(item)
            else:
                skipped_count += 1

        res = self._ingest_items(qualified_items, on_item_processed)
        res["skipped_low_qa"] = skipped_count
        return res

    def _ingest_items(
        self, items: List[ZoteroItem], on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ) -> Dict[str, Any]:
        processed = 0
        skipped_no_text = 0

        for item in items:
            # 1. Clear existing chunks for this item (Idempotency - Issue #112)
            self.vector_repo.delete_chunks_by_item(item.key)

            # 2. Extract text from attachments (PDFs)
            text = self.attachment_service.get_fulltext(item.key)
            if not text:
                skipped_no_text += 1
                if on_item_processed:
                    on_item_processed(item)
                continue

            # 3. Chunk text
            chunks_text = self._chunk_text(text)

            # 4. Generate embeddings
            embeddings = self.embedding_provider.embed_batch(chunks_text)

            # 5. Store in vector repo
            vector_chunks = []
            for i, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings)):
                vector_chunks.append(
                    VectorChunk(
                        item_key=item.key, chunk_index=i, text=chunk_text, embedding=embedding
                    )
                )

            self.vector_repo.store_chunks(vector_chunks)
            processed += 1
            
            if on_item_processed:
                on_item_processed(item)

        return {"processed": processed, "skipped_no_text": skipped_no_text}

    def purge(
        self,
        purge_all: bool = False,
        item_key: Optional[str] = None,
        collection_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Remove chunks from the vector store based on criteria.
        """
        deleted_count = 0
        if purge_all:
            self.vector_repo.purge_all()
            return {"deleted_all": True}
        
        if item_key:
            self.vector_repo.delete_chunks_by_item(item_key)
            return {"deleted_item": item_key}
            
        if collection_key:
            col_id = self.gateway.get_collection_id_by_name(collection_key) or collection_key
            items = list(self.gateway.get_items_in_collection(col_id))
            for item in items:
                self.vector_repo.delete_chunks_by_item(item.key)
                deleted_count += 1
            return {"deleted_collection": collection_key, "items_cleared": deleted_count}
            
        return {"error": "No purge criteria provided"}

    def query(self, prompt: str, top_k: int = 5) -> List[SearchResult]:
        """
        Perform semantic search against the vector store.
        """
        embedding = self.embedding_provider.embed_text(prompt)
        results = self.vector_repo.search(embedding, top_k=top_k)

        # Hydrate results with full items
        for result in results:
            result.item = self.gateway.get_item(result.item_key)

        return results

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
