import logging
from typing import Any, Callable, Dict, List, Optional

from zotero_cli.core.interfaces import (
    EmbeddingProvider,
    FullTextProvider,
    RAGService,
    TextSplitter,
    VectorRepository,
    ZoteroGateway,
)
from zotero_cli.core.models import (
    ScreeningStatus,
    SearchResult,
    VectorChunk,
    VerifiedSearchResult,
)
from zotero_cli.core.utils.sdb_parser import parse_sdb_note
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class FixedSizeChunker(TextSplitter):
    """
    Primitive chunking strategy implementation [SPEC-RAG-003].
    """

    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        return [
            text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)
        ]


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
        fulltext_provider: FullTextProvider,
        text_splitter: Optional[TextSplitter] = None,
    ):
        self.gateway = gateway
        self.vector_repo = vector_repo
        self.embedding_provider = embedding_provider
        self.fulltext_provider = fulltext_provider
        self.text_splitter = text_splitter or FixedSizeChunker()

    def ingest(
        self,
        item_keys: List[str],
        prune: bool = False,
        min_qa_score: Optional[float] = None,
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
    ) -> Dict[str, Any]:
        """
        Refactored ingestion with pre-selected item keys [SPEC-RAG-001].
        """
        # 1. Full Prune if requested
        if prune:
            logger.info("Pruning entire vector store before ingestion.")
            self.vector_repo.purge_all()

        stats = {
            "processed": 0,
            "skipped_no_text": 0,
            "skipped_low_qa": 0,
        }

        for key in item_keys:
            item = self.gateway.get_item(key)
            if not item:
                continue

            # A. Filter: QA Score [SPEC-RAG-002]
            if min_qa_score is not None:
                qa_score = self._get_item_max_qa_score(item)
                if qa_score < min_qa_score:
                    stats["skipped_low_qa"] += 1
                    if on_item_processed:
                        on_item_processed(item)
                    continue

            # B. Ingest
            # Idempotency: Clear existing chunks for this item if not pruned globally
            if not prune:
                self.vector_repo.delete_chunks_by_item(item.key)

            # Extract text
            text = self.fulltext_provider.get_fulltext(item.key)
            if not text:
                stats["skipped_no_text"] += 1
                if on_item_processed:
                    on_item_processed(item)
                continue

            # Chunk, Embed & Store
            chunks_text = self.text_splitter.split_text(text)
            embeddings = self.embedding_provider.embed_batch(chunks_text)

            vector_chunks = []
            for i, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings)):
                vector_chunks.append(
                    VectorChunk(
                        item_key=item.key, chunk_index=i, text=chunk_text, embedding=embedding
                    )
                )

            self.vector_repo.store_chunks(vector_chunks)
            stats["processed"] += 1

            if on_item_processed:
                on_item_processed(item)

        return stats

    def _get_item_max_qa_score(self, item: ZoteroItem) -> float:
        """
        Extracts max QA score using the high-fidelity path [SPEC-RAG-002].
        Path: data -> quality_assessment -> total
        """
        max_score = -1.0
        children = self.gateway.get_item_children(item.key)

        for child_raw in children:
            if child_raw.get("data", {}).get("itemType") == "note":
                note_content = child_raw.get("data", {}).get("note", "")
                parsed = parse_sdb_note(note_content)
                if parsed and parsed.get("action") == "data_extraction":
                    # Correct path per [SPEC-RAG-002]
                    data_block = parsed.get("data", {})
                    qa_block = data_block.get("quality_assessment", {})
                    score = qa_block.get("total")

                    # Fallback to legacy path if new path is missing
                    if score is None:
                        score = parsed.get("quality_score") or data_block.get("quality_score")

                    if score is not None:
                        try:
                            f_score = float(score)
                            if f_score > max_score:
                                max_score = f_score
                        except (ValueError, TypeError):
                            continue
        return max_score

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

    def verify_results(self, results: List[SearchResult]) -> List[VerifiedSearchResult]:
        """
        Verifies search results for academic integrity and metadata completeness.
        """
        verified_results = []
        for res in results:
            item = res.item or self.gateway.get_item(res.item_key)

            is_verified = True
            errors = []

            if not item:
                is_verified = False
                errors.append("Item not found in Zotero")
            else:
                if not item.has_identifier():
                    is_verified = False
                    errors.append("Missing DOI or arXiv ID")
                if not item.title:
                    is_verified = False
                    errors.append("Missing Title")
                if not item.abstract:
                    is_verified = False
                    errors.append("Missing Abstract")

            # Screening status
            screening_status = ScreeningStatus.UNKNOWN
            if item:
                if "rsl:include" in item.tags:
                    screening_status = ScreeningStatus.ACCEPTED
                elif "rsl:exclude" in item.tags:
                    screening_status = ScreeningStatus.REJECTED
                else:
                    # Check for screening note
                    children = self.gateway.get_item_children(item.key)
                    for child in children:
                        if child.get("data", {}).get("itemType") == "note":
                            note_text = child.get("data", {}).get("note", "")
                            parsed = parse_sdb_note(note_text)
                            if parsed and parsed.get("action") == "screening_decision":
                                decision = parsed.get("decision")
                                if decision == "accepted":
                                    screening_status = ScreeningStatus.ACCEPTED
                                elif decision == "rejected":
                                    screening_status = ScreeningStatus.REJECTED
                                break

            # Citation key
            citation_key = getattr(item, 'raw_data', {}).get('data', {}).get('citationKey')
            if not citation_key and item and item.extra:
                for line in item.extra.split("\n"):
                    if line.lower().startswith("citation key:"):
                        citation_key = line.split(":", 1)[1].strip()
                        break

            verified_results.append(
                VerifiedSearchResult(
                    item_key=res.item_key,
                    text=res.text,
                    score=res.score,
                    metadata=res.metadata,
                    item=item,
                    is_verified=is_verified,
                    verification_errors=errors,
                    screening_status=screening_status,
                    citation_key=citation_key
                )
            )
        return verified_results

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
