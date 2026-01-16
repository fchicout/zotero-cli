from abc import ABC, abstractmethod
from typing import Optional, Iterator, List, Dict, Any
from .models import ResearchPaper
from .zotero_item import ZoteroItem

class ZoteroGateway(ABC):
    @abstractmethod
    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        """
        Retrieves the ID of a Zotero collection by its name.
        Returns the collection ID if found, otherwise None.
        """
        pass

    @abstractmethod
    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all groups a user belongs to.
        """
        pass

    @abstractmethod
    def get_all_collections(self) -> List[Dict[str, Any]]:
        """
        Retrieves all collections in the library.
        """
        pass

    @abstractmethod
    def create_collection(self, name: str) -> Optional[str]:
        """
        Creates a new Zotero collection with the given name.
        Returns the new collection ID if successful, otherwise None.
        """
        pass

    @abstractmethod
    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a collection object by key.
        """
        pass

    @abstractmethod
    def delete_collection(self, collection_key: str, version: int) -> bool:
        """
        Deletes a collection by key.
        Returns True on success.
        """
        pass

    @abstractmethod
    def rename_collection(self, collection_key: str, version: int, name: str) -> bool:
        """
        Renames a collection.
        Returns True on success.
        """
        pass

    @abstractmethod
    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        """
        Creates a new Zotero item based on the provided ResearchPaper data
        and adds it to the specified collection.
        Returns True on success, False otherwise.
        """
        pass

    @abstractmethod
    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        """
        Creates a new item with raw dictionary data.
        Returns the new Item Key if successful.
        """
        pass

    @abstractmethod
    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        """
        Updates an item with raw dictionary data (PATCH).
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

    @abstractmethod
    def get_items_in_collection(self, collection_id: str) -> Iterator[ZoteroItem]:
        """
        Retrieves all items in a specified collection.
        """
        pass

    @abstractmethod
    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        """
        Retrieves child items (like attachments) for a given item.
        """
        pass

    @abstractmethod
    def get_tags(self) -> List[str]:
        """
        Retrieves all unique tags in the library.
        """
        pass

    @abstractmethod
    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        """
        Retrieves all items with a specific tag.
        """
        pass

    @abstractmethod
    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        """
        Retrieves a single item by its key.
        """
        pass

    @abstractmethod
    def delete_item(self, item_key: str, version: int) -> bool:
        """
        Deletes an item from the library.
        Requires item_key and current version.
        Returns True on success, False otherwise.
        """
        pass

    @abstractmethod
    def upload_attachment(self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf") -> bool:
        """
        Uploads a file as an attachment to a parent item.
        Handles the Zotero 3-step upload process.
        """
        pass

    @abstractmethod
    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        """
        Creates a child note for a parent item.
        'note_content' should be HTML.
        Returns True on success, False otherwise.
        """
        pass

    @abstractmethod
    def update_note(self, note_key: str, version: int, note_content: str) -> bool:
        """
        Updates an existing note.
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