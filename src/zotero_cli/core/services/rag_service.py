import logging
import re
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
from zotero_cli.core.services.slr.citation_service import CitationService
from zotero_cli.core.services.slr.orchestrator import SLROrchestrator
from zotero_cli.core.utils.sdb_parser import parse_sdb_note
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class FixedSizeChunker(TextSplitter):
    """
    Primitive chunking strategy implementation [SPEC-RAG-003].
    """

    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size

    def split_text(self, text: str, context_title: Optional[str] = None) -> List[str]:
        if not text:
            return []
        return [
            text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)
        ]


class MarkdownRecursiveSplitter(TextSplitter):
    """
    High-fidelity structural splitter [SPEC-RAG-002].
    Uses Markdown headers and paragraphs to preserve semantic meaning.
    Injects [Source] and [Section] breadcrumbs into every chunk.
    """

    def __init__(self, chunk_size: int = 1500):
        self.chunk_size = chunk_size
        self.header_regex = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

    def split_text(self, text: str, context_title: Optional[str] = None) -> List[str]:
        if not text:
            return []

        chunks = []
        current_section = "Introduction"
        
        # 1. Split into Section Blocks based on headers
        sections = []
        last_pos = 0
        for match in self.header_regex.finditer(text):
            if match.start() > last_pos:
                sections.append((current_section, text[last_pos:match.start()]))
            
            current_section = match.group(2).strip()
            last_pos = match.end()
        
        sections.append((current_section, text[last_pos:]))

        # 2. Further split large sections into chunks with breadcrumbs
        for section_title, content in sections:
            paragraphs = content.split("\n\n")
            current_chunk = []
            current_length = 0
            
            breadcrumb = f"[Source: {context_title or 'Unknown'}] [Section: {section_title}]\n\n"
            breadcrumb_len = len(breadcrumb)

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                if len(para) > self.chunk_size:
                    if current_chunk:
                        chunks.append(breadcrumb + "\n\n".join(current_chunk))
                    
                    for i in range(0, len(para), self.chunk_size - breadcrumb_len):
                        chunks.append(breadcrumb + para[i : i + (self.chunk_size - breadcrumb_len)])
                    
                    current_chunk = []
                    current_length = 0
                    continue

                if current_length + len(para) > (self.chunk_size - breadcrumb_len):
                    chunks.append(breadcrumb + "\n\n".join(current_chunk))
                    current_chunk = [para]
                    current_length = len(para)
                else:
                    current_chunk.append(para)
                    current_length += len(para) + 2

            if current_chunk:
                chunks.append(breadcrumb + "\n\n".join(current_chunk))

        return chunks


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
        # Use High-Fidelity Splitter by default
        self.text_splitter = text_splitter or MarkdownRecursiveSplitter()
        self.citation_service = CitationService()
        self.orchestrator = SLROrchestrator(gateway)

    def ingest(
        self,
        item_keys: List[str],
        prune: bool = False,
        min_qa_score: Optional[float] = None,
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
    ) -> Dict[str, Any]:
        """
        Refactored ingestion with parallel processing and structural splitting [SPEC-RAG-001].
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if prune:
            logger.info("Pruning entire vector store before ingestion.")
            self.vector_repo.purge_all()

        stats = {"processed": 0, "skipped_no_text": 0, "skipped_low_qa": 0}
        all_vector_chunks = []

        def process_item(key: str):
            item = self.gateway.get_item(key)
            if not item: return None

            qa_score = self._get_item_max_qa_score(item)
            citation_key = self.citation_service.resolve_citation_key(item)
            target_phase = self.orchestrator.resolve_target_phase(item.key, default_qa_threshold=min_qa_score)

            if min_qa_score is not None:
                if qa_score < min_qa_score:
                    return {"status": "low_qa", "item": item}

            text = self.fulltext_provider.get_fulltext(item.key)
            if not text:
                return {"status": "no_text", "item": item}

            # Structural Splitting with breadcrumbs
            chunks_text = self.text_splitter.split_text(text, context_title=item.title)
            embeddings = self.embedding_provider.embed_batch(chunks_text)

            item_chunks = []
            for i, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings)):
                item_chunks.append(
                    VectorChunk(
                        item_key=item.key,
                        chunk_index=i,
                        text=chunk_text,
                        embedding=embedding,
                        citation_key=citation_key,
                        qa_score=qa_score if qa_score >= 0 else None,
                        phase_folder=target_phase,
                    )
                )
            return {"status": "success", "item": item, "chunks": item_chunks}

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_key = {executor.submit(process_item, key): key for key in item_keys}
            for future in as_completed(future_to_key):
                result = future.result()
                if not result: continue
                
                item = result["item"]
                if result["status"] == "success":
                    if not prune: self.vector_repo.delete_chunks_by_item(item.key)
                    all_vector_chunks.extend(result["chunks"])
                    stats["processed"] += 1
                else:
                    stats[f"skipped_{result['status']}"] += 1

                if on_item_processed: on_item_processed(item)

        if all_vector_chunks:
            self.vector_repo.store_chunks(all_vector_chunks)

        return stats

    def _get_item_max_qa_score(self, item: ZoteroItem) -> float:
        """
        Extracts QA score from the dedicated 'quality_assessment' phase note.
        """
        max_score = -1.0
        children = self.gateway.get_item_children(item.key)
        for child_raw in children:
            if child_raw.get("data", {}).get("itemType") == "note":
                note_content = child_raw.get("data", {}).get("note", "")
                parsed = parse_sdb_note(note_content)
                if not parsed: continue

                is_qa_phase = parsed.get("phase") == "quality_assessment"
                is_ext_action = parsed.get("action") == "data_extraction"
                
                if is_qa_phase or is_ext_action:
                    qa_block = parsed.get("data", {}).get("quality_assessment") or parsed.get("quality_assessment")
                    score = qa_block.get("total") if isinstance(qa_block, dict) else (parsed.get("quality_score") or parsed.get("data", {}).get("quality_score"))
                    
                    if score is not None:
                        try:
                            f_score = float(score)
                            if f_score > max_score: max_score = f_score
                        except (ValueError, TypeError): continue
        return max_score

    def purge(self, purge_all: bool = False, item_key: Optional[str] = None, collection_key: Optional[str] = None) -> Dict[str, Any]:
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
            return {"deleted_collection": collection_key, "items_cleared": len(items)}
        return {"error": "No purge criteria provided"}

    def verify_results(self, results: List[SearchResult]) -> List[VerifiedSearchResult]:
        verified_results = []
        for res in results:
            item = res.item or self.gateway.get_item(res.item_key)
            is_verified = True
            errors = []
            if not item:
                is_verified = False
                errors.append("Item not found")
            else:
                if not item.has_identifier(): is_verified, errors.append("Missing ID")
                if not item.title: is_verified, errors.append("Missing Title")

            screening_status = ScreeningStatus.UNKNOWN
            citation_key = self.citation_service.resolve_citation_key(item) if item else None
            verified_results.append(VerifiedSearchResult(
                item_key=res.item_key, text=res.text, score=res.score, metadata=res.metadata,
                item=item, is_verified=is_verified, verification_errors=errors,
                screening_status=screening_status, citation_key=citation_key
            ))
        return verified_results

    def query(self, prompt: str, top_k: int = 5) -> List[SearchResult]:
        embedding = self.embedding_provider.embed_text(prompt)
        results = self.vector_repo.search(embedding, top_k=top_k)
        for result in results:
            result.item = self.gateway.get_item(result.item_key)
        return results

    def get_context(self, item_key: str) -> str:
        chunks = self.vector_repo.get_chunks_by_item(item_key)
        return "\n\n".join([c.text for c in chunks])
