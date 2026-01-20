from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional

from .models import ResearchPaper, ZoteroQuery
from .zotero_item import ZoteroItem


class ItemRepository(ABC):
    @abstractmethod
    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        pass

    @abstractmethod
    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
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
