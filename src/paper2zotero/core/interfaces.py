from abc import ABC, abstractmethod
from typing import Optional, Iterator, List, Dict, Any
from .models import ResearchPaper

class ZoteroGateway(ABC):
    @abstractmethod
    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        """
        Retrieves the ID of a Zotero collection by its name.
        Returns the collection ID if found, otherwise None.
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
    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        """
        Creates a new Zotero item based on the provided ResearchPaper data
        and adds it to the specified collection.
        Returns True on success, False otherwise.
        """
        pass

    @abstractmethod
    def get_items_in_collection(self, collection_id: str) -> Iterator[Dict[str, Any]]:
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
    def delete_item(self, item_key: str, version: int) -> bool:
        """
        Deletes an item by its key. Requires the current item version.
        """
        pass

class ArxivGateway(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 100) -> Iterator[ResearchPaper]:
        """
        Searches arXiv for papers matching the query and returns an iterator of ResearchPaper objects.
        """
        pass

class BibtexGateway(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        """
        Parses a BibTeX file and returns an iterator of ResearchPaper objects.
        """
        pass
