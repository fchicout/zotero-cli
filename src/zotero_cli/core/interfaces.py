from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from .models import Job, ResearchPaper, SearchResult, VectorChunk, ZoteroQuery
from .zotero_item import ZoteroItem


class ItemRepository(ABC):
    @abstractmethod
    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        pass

    @abstractmethod
    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        pass

    @abstractmethod
    def get_item_template(self, item_type: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        pass

    @abstractmethod
    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def delete_item(self, item_key: str, version: int) -> bool:
        pass

    @abstractmethod
    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        pass

    @abstractmethod
    def get_items_by_doi(self, doi: str) -> Iterator[ZoteroItem]:
        pass

    @abstractmethod
    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        pass


class CollectionRepository(ABC):
    @abstractmethod
    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        pass

    @abstractmethod
    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        pass

    @abstractmethod
    def delete_collection(self, collection_key: str, version: int) -> bool:
        pass

    @abstractmethod
    def rename_collection(self, collection_key: str, version: int, name: str) -> bool:
        pass

    @abstractmethod
    def get_all_collections(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_items_in_collection(
        self, collection_id: str, top_only: bool = False
    ) -> Iterator[ZoteroItem]:
        pass


class TagRepository(ABC):
    @abstractmethod
    def get_tags(self) -> List[str]:
        pass

    @abstractmethod
    def get_tags_for_item(self, item_key: str) -> List[str]:
        pass

    @abstractmethod
    def add_tags(self, item_key: str, tags: List[str]) -> bool:
        pass

    @abstractmethod
    def delete_tags(self, tags: List[str], version: int) -> bool:
        pass


class NoteRepository(ABC):
    @abstractmethod
    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        pass

    @abstractmethod
    def update_note(self, note_key: str, version: int, note_content: str) -> bool:
        pass

    @abstractmethod
    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        pass


class AttachmentRepository(ABC):
    @abstractmethod
    def upload_attachment(
        self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf"
    ) -> bool:
        pass

    @abstractmethod
    def download_attachment(self, item_key: str, save_path: str) -> bool:
        pass

    @abstractmethod
    def update_attachment_link(self, item_key: str, version: int, new_path: str) -> bool:
        pass


class JobRepository(ABC):
    @abstractmethod
    def enqueue(self, job: Job) -> int:
        pass

    @abstractmethod
    def get_next_pending(self, task_type: str) -> Optional[Job]:
        pass

    @abstractmethod
    def update_job(self, job: Job) -> bool:
        pass

    @abstractmethod
    def get_job(self, job_id: int) -> Optional[Job]:
        pass

    @abstractmethod
    def list_jobs(self, task_type: Optional[str] = None, limit: int = 100) -> List[Job]:
        pass


class MetadataProvider(ABC):
    @abstractmethod
    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        pass


class ArxivGateway(ABC):
    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> Iterator[ResearchPaper]:
        pass


class BibtexGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        pass

    @abstractmethod
    def write_file(self, file_path: str, papers: List[ResearchPaper]) -> bool:
        pass


class RisGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        pass


class SpringerCsvGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        pass


class IeeeCsvGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        pass


class CanonicalCsvGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        pass


class ZoteroGateway(
    ItemRepository, CollectionRepository, TagRepository, NoteRepository, AttachmentRepository
):
    """
    Unified Gateway interface for Zotero API.
    Inherits from specific repositories to enforce contract.
    """

    @abstractmethod
    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        pass

    @abstractmethod
    def verify_credentials(self) -> bool:
        pass

    @abstractmethod
    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_all_items(self) -> Iterator[ZoteroItem]:
        pass

    @abstractmethod
    def get_orphan_items(self) -> Iterator[ZoteroItem]:
        pass


class PDFResolver(ABC):
    """
    Interface for resolving and downloading PDFs from various sources.
    """

    @abstractmethod
    async def resolve(self, item: ZoteroItem) -> Optional[Path]:
        """
        Resolves a PDF for the given item.
        Raises ResolutionError if a technical error occurs during resolution.
        Returns None if the PDF could not be found via this resolver.
        """
        pass


class ResolutionError(Exception):
    """
    Exception raised when a PDF resolution fails due to a technical error.
    """

    pass


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class VectorRepository(ABC):
    @abstractmethod
    def store_chunks(self, chunks: List[VectorChunk]) -> bool:
        pass

    @abstractmethod
    def search(self, embedding: List[float], top_k: int = 5) -> List[SearchResult]:
        pass

    @abstractmethod
    def get_chunks_by_item(self, item_key: str) -> List[VectorChunk]:
        pass

    @abstractmethod
    def delete_chunks_by_item(self, item_key: str) -> bool:
        pass

    @abstractmethod
    def purge_all(self) -> bool:
        pass


class RAGService(ABC):
    @abstractmethod
    def ingest_collection(
        self,
        collection_key: str,
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def ingest_item(
        self, item_key: str, on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def ingest_approved(
        self, on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def ingest_by_qa_score(
        self, min_score: float, on_item_processed: Optional[Callable[[ZoteroItem], None]] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def query(self, prompt: str, top_k: int = 5) -> List[SearchResult]:
        pass

    @abstractmethod
    def get_context(self, item_key: str) -> str:
        pass

    @abstractmethod
    def purge(
        self,
        purge_all: bool = False,
        item_key: Optional[str] = None,
        collection_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        pass


class ExtractionService(ABC):
    validator: Any

    @abstractmethod
    def save_extraction(
        self,
        item_key: str,
        data: Dict[str, Any],
        schema_version: str,
        agent: str = "zotero-cli",
        persona: str = "unknown",
    ) -> bool:
        pass

    @abstractmethod
    def export_matrix(
        self,
        items: List[Any],
        output_format: str = "csv",
        persona: str = "unknown",
        output_path: Optional[str] = None,
    ) -> str:
        pass


class ScreeningService(ABC):
    @abstractmethod
    def get_pending_items(self, collection_id: str) -> List[ZoteroItem]:
        pass

    @abstractmethod
    def record_decision(
        self,
        item_key: str,
        decision: str,
        code: str,
        reason: str = "",
        source_collection: Optional[str] = None,
        target_collection: Optional[str] = None,
        agent: str = "zotero-cli",
        persona: str = "unknown",
        phase: str = "title_abstract",
        evidence: Optional[str] = None,
    ) -> bool:
        pass


class SnowballGraphService(ABC):
    STATUS_ACCEPTED = "ACCEPTED"
    STATUS_REJECTED = "REJECTED"
    graph: Any

    @abstractmethod
    def get_ranked_candidates(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_status(self, doi: str, status: str):
        pass

    @abstractmethod
    def save_graph(self):
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def to_mermaid(self) -> str:
        pass


class OpenerService(ABC):
    @abstractmethod
    def open_file(self, path: str) -> bool:
        pass


class AuditService(ABC):
    @abstractmethod
    def audit_manuscript(self, path: Path) -> Dict[str, Any]:
        pass
