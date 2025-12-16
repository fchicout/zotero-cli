from abc import ABC, abstractmethod
from typing import Optional, Iterator
from .models import ArxivPaper

class ZoteroGateway(ABC):
    @abstractmethod
    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        """
        Retrieves the ID of a Zotero collection by its name.
        Returns the collection ID if found, otherwise None.
        """
        pass

    @abstractmethod
    def create_item(self, paper: ArxivPaper, collection_id: str) -> bool:
        """
        Creates a new Zotero item based on the provided ArxivPaper data
        and adds it to the specified collection.
        Returns True on success, False otherwise.
        """
        pass

class ArxivGateway(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 100) -> Iterator[ArxivPaper]:
        """
        Searches arXiv for papers matching the query and returns an iterator of ArxivPaper objects.
        """
        pass
