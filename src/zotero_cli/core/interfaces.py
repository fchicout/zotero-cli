from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .models import (
    Job,
    ResearchPaper,
    WriteOutcome,
    WriteStatus,
    ZoteroQuery,
)
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
    def update_items(self, items_data: List[Dict[str, Any]]) -> bool:
        """
        Updates multiple items in a single request.
        Each dict must contain 'key' and 'version'.
        """
        pass

    @abstractmethod
    def delete_item(self, item_key: str, version: int) -> bool:
        pass

    @abstractmethod
    def trash_item(self, item_key: str, version: int = 0) -> bool:
        """Moves the item to Zotero's trash (recoverable, unlike `delete_item`).
        A falsy `version` means "whatever the current one is"."""

    @abstractmethod
    def restore_item(self, item_key: str, version: int = 0) -> bool:
        """Takes the item out of the trash."""

    @abstractmethod
    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        pass

    @abstractmethod
    def get_items_by_doi(self, doi: str) -> Iterator[ZoteroItem]:
        pass

    @abstractmethod
    def get_all_items(self) -> Iterator[ZoteroItem]:
        """
        Iterates every item in the library. Exposed here (mirroring
        ZoteroGateway's own get_all_items) so a caller holding only the
        narrower ItemRepository can build a one-time in-memory index
        (e.g. by DOI) instead of resorting to a per-item get_items_by_doi
        scan in a loop - Issue #267.
        """
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
    def update_note(
        self, note_key: str, version: int, note_content: str, parent_item_key: Optional[str] = None
    ) -> bool:
        pass

    def create_note_result(self, parent_item_key: str, note_content: str) -> WriteOutcome:
        """`create_note`, but saying whether the note was stored (Issue #577). The default
        only knows the boolean; the Web API client overrides it with the real outcome."""
        stored = self.create_note(parent_item_key, note_content)
        return WriteOutcome(WriteStatus.APPLIED if stored else WriteStatus.NOT_APPLIED)

    def update_note_result(
        self,
        note_key: str,
        version: int,
        note_content: str,
        parent_item_key: Optional[str] = None,
        retry_on_conflict: bool = False,
    ) -> WriteOutcome:
        """`update_note` with the real outcome. `version` is the note's own version: a
        write against a newer note is a `CONFLICT`, never an overwrite, unless
        `retry_on_conflict` opts in to re-reading the version and writing once more."""
        stored = self.update_note(note_key, version, note_content, parent_item_key)
        return WriteOutcome(WriteStatus.APPLIED if stored else WriteStatus.NOT_APPLIED)

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

    @abstractmethod
    def get_annotations(self, item_key: str) -> List[Dict[str, Any]]:
        """The PDF annotations (highlights, notes, ...) of an item's PDF attachments, or of
        the attachment itself if `item_key` names one, in reading order, as the dicts
        `zotero_cli.core.annotations.build` makes. Empty when there are none."""
        pass


class JobRepository(ABC):
    @abstractmethod
    def enqueue(self, job: Job) -> int:
        pass

    @abstractmethod
    def get_next_pending(self, task_type: str, library_id: Optional[str] = None) -> Optional[Job]:
        pass

    @abstractmethod
    def update_job(self, job: Job) -> bool:
        pass

    @abstractmethod
    def get_job(self, job_id: int) -> Optional[Job]:
        pass

    @abstractmethod
    def list_jobs(
        self, task_type: Optional[str] = None, library_id: Optional[str] = None, limit: int = 100
    ) -> List[Job]:
        pass


class MetadataProvider(ABC):
    @abstractmethod
    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        pass


class SearchableMetadataProvider(ABC):
    """
    Optional capability mixin for a MetadataProvider whose underlying API
    supports free-text/topic search, not just resolving an already-known
    identifier (Issue #179). Not every MetadataProvider can do this (most
    of this project's 11 metadata sources are ID-lookup-only), so this is
    a separate, additionally-inherited interface rather than a method on
    MetadataProvider itself - mirrors ArxivGateway.search's shape below so
    callers can treat every searchable source the same way.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> Iterator[ResearchPaper]:
        pass


class CountableMetadataProvider(ABC):
    """
    Optional capability mixin for a MetadataProvider (typically also a
    SearchableMetadataProvider) whose underlying API can report a query's
    total result count cheaply, without paginating the full result set
    (Issue #190) - mirrors ArxivGateway.count's shape. Lets a caller build a
    read-only "About N results" exploratory-search UI without the
    bandwidth/rate-limit cost of a capped fetch-and-count stopgap.
    """

    @abstractmethod
    def count(self, query: str) -> int:
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

    @abstractmethod
    def count(self, query: str) -> int:
        """
        Returns the total result count for a query without fetching
        individual results (Issue #181) - for a read-only "About N
        results" exploratory-search UI that shouldn't pay the bandwidth/
        rate-limit cost of materializing full ResearchPaper objects.
        """
        pass


class BibliographyFormatter(ABC):
    @abstractmethod
    def format(self, bibtex: str, style: str, render: str = "plain") -> str:
        """BibTeX source as a bibliography in a CSL style (plain, markdown or html)."""


class BibtexGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        pass

    @abstractmethod
    def serialize(self, papers: List[ResearchPaper]) -> str:
        pass

    @abstractmethod
    def write_file(self, file_path: str, papers: List[ResearchPaper]) -> bool:
        pass


class RisGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        pass

    @abstractmethod
    def serialize(self, papers: List[ResearchPaper]) -> str:
        pass

    @abstractmethod
    def write_file(self, file_path: str, papers: List[ResearchPaper]) -> bool:
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


class ItemSearch(ABC):
    """Searching items: by keyword and filters, and (offline) by PDF text."""

    @abstractmethod
    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        pass

    def search_fulltext(
        self, text: str, query: Optional[ZoteroQuery] = None
    ) -> List[Tuple[ZoteroItem, float]]:
        """Items whose PDF text contains every word of `text`, best match first, with a
        relevance score (higher is better); `query` adds the usual filters (tag, type,
        collection, ...). Only the offline gateway has Zotero's index to read, so the
        default says so (Issue #560)."""
        from zotero_cli.core.exceptions import UsageError

        del text, query  # the signature is the contract; only the offline gateway uses them
        raise UsageError("Full-text search reads Zotero's local index: run it with --offline.")


class ZoteroGateway(
    ItemRepository,
    CollectionRepository,
    TagRepository,
    NoteRepository,
    AttachmentRepository,
    ItemSearch,
):
    """
    Unified Gateway interface for Zotero API.
    Inherits from specific repositories to enforce contract.
    """

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
    def get_orphan_items(self, top_only: bool = False) -> Iterator[ZoteroItem]:
        pass

    @abstractmethod
    def get_trash_items(self) -> Iterator[ZoteroItem]:
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


class FullTextProvider(ABC):
    """
    Interface for providing full text content for research items [SPEC-RAG-003].
    """

    @abstractmethod
    def get_fulltext(self, item_key: str) -> Optional[str]:
        pass
