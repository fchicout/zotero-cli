from abc import ABC, abstractmethod
from typing import Optional, Iterator, List, Dict, Any
from .models import ResearchPaper, ZoteroQuery
from .zotero_item import ZoteroItem

class ItemRepository(ABC):
    @abstractmethod
    def get_item(self, item_key: str) -> Optional[ZoteroItem]: pass
    
    @abstractmethod
    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool: pass
    
    @abstractmethod
    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]: pass
    
    @abstractmethod
    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool: pass
    
    @abstractmethod
    def delete_item(self, item_key: str, version: int) -> bool: pass

class CollectionRepository(ABC):
    @abstractmethod
    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]: pass
    
    @abstractmethod
    def get_collection_id_by_name(self, name: str) -> Optional[str]: pass
    
    @abstractmethod
    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]: pass
    
    @abstractmethod
    def delete_collection(self, collection_key: str, version: int) -> bool: pass
    
    @abstractmethod
    def get_all_collections(self) -> List[Dict[str, Any]]: pass
    
    @abstractmethod
    def get_items_in_collection(self, collection_id: str, top_only: bool = False) -> Iterator[ZoteroItem]: pass

class TagRepository(ABC):
    @abstractmethod
    def get_tags(self) -> List[str]: pass
    
    @abstractmethod
    def get_tags_for_item(self, item_key: str) -> List[str]: pass
    
    @abstractmethod
    def delete_tags(self, tags: List[str], version: int) -> bool: pass

class NoteRepository(ABC):
    @abstractmethod
    def create_note(self, parent_item_key: str, note_content: str) -> bool: pass
    
    @abstractmethod
    def update_note(self, note_key: str, version: int, note_content: str) -> bool: pass
    
    @abstractmethod
    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]: pass

class AttachmentRepository(ABC):
    @abstractmethod
    def upload_attachment(self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf") -> bool: pass

class ZoteroGateway(ItemRepository, CollectionRepository, TagRepository, NoteRepository, AttachmentRepository, ABC):
    @abstractmethod
    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        """
        Performs a library search based on the provided query object.
        """
        pass

    @abstractmethod
    def get_tags_in_collection(self, collection_key: str) -> List[str]:
        """Retrieves tags assigned to items in a collection."""
        pass

    @abstractmethod
    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        """
        Retrieves all items with a specific tag.
        """
        pass

    @abstractmethod
    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all groups a user belongs to.
        """
        pass

    @abstractmethod
    def get_top_collections(self) -> List[Dict[str, Any]]:
        """Retrieves top-level collections."""
        pass

    @abstractmethod
    def get_subcollections(self, collection_key: str) -> List[Dict[str, Any]]:
        """Retrieves subcollections of a specific collection."""
        pass

    @abstractmethod
    def get_saved_searches(self) -> List[Dict[str, Any]]:
        """Retrieves saved searches."""
        pass

    @abstractmethod
    def get_trash_items(self) -> Iterator[ZoteroItem]:
        """Retrieves items in the trash."""
        pass

    @abstractmethod
    def rename_collection(self, collection_key: str, version: int, name: str) -> bool:
        """
        Renames a collection.
        Returns True on success.
        """
        pass

    @abstractmethod
    def update_item_collections(self, item_key: str, version: int, collections: List[str]) -> bool:
        """
        Updates the list of collections an item belongs to.
        Requires item_key, current version, and the new list of collection IDs.
        Returns True on success, False otherwise.
        """
        pass

    @abstractmethod
    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        """
        Updates specific metadata fields of an item.
        Requires item_key, current version, and a dictionary of fields to update.
        Returns True on success, False otherwise.
        """
        pass

class ArxivGateway(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 100, sort_by: str = "relevance", sort_order: str = "descending") -> Iterator[ResearchPaper]:
        """
        Searches arXiv for papers matching the query and returns an iterator of ResearchPaper objects.
        sort_by: "relevance", "lastUpdatedDate", "submittedDate"
        sort_order: "ascending", "descending"
        """
        pass

class BibtexGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        """
        Parses a BibTeX file and returns an iterator of ResearchPaper objects.
        """
        pass

class RisGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        """
        Parses a RIS file and returns an iterator of ResearchPaper objects.
        """
        pass

class SpringerCsvGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        """
        Parses a Springer CSV file and returns an iterator of ResearchPaper objects.
        """
        pass

class IeeeCsvGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        """
        Parses an IEEE CSV file and returns an iterator of ResearchPaper objects.
        """
        pass

class MetadataProvider(ABC):
    @abstractmethod
    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves full paper metadata (including references) for the given identifier (DOI).
        Returns a ResearchPaper object if found, otherwise None.
        """
        pass