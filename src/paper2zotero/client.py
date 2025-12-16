from typing import Optional
from paper2zotero.core.interfaces import ZoteroGateway, ArxivGateway
from paper2zotero.core.models import ArxivPaper

class CollectionNotFoundError(Exception):
    """Raised when the specified Zotero collection cannot be found."""
    pass

class Arxiv2ZoteroClient:
    def __init__(self, zotero_gateway: ZoteroGateway, arxiv_gateway: Optional[ArxivGateway] = None):
        self.zotero_gateway = zotero_gateway
        self.arxiv_gateway = arxiv_gateway

    def add_paper(self, arxiv_id: str, abstract: str, title: str, folder_name: str) -> bool:
        """
        Adds a single paper to a Zotero collection.
        """
        # 1. Resolve Collection ID
        collection_id = self.zotero_gateway.get_collection_id_by_name(folder_name)
        if not collection_id:
            raise CollectionNotFoundError(f"Collection '{folder_name}' not found.")

        # 2. Create Domain Model
        paper = ArxivPaper(arxiv_id=arxiv_id, title=title, abstract=abstract)

        # 3. Create Item via Gateway
        success = self.zotero_gateway.create_item(paper, collection_id)
        
        return success

    def import_from_query(self, query: str, folder_name: str, limit: int = 100, verbose: bool = False) -> int:
        """
        Searches arXiv and imports results into Zotero.
        Returns the number of successfully imported items.
        """
        if not self.arxiv_gateway:
            raise ValueError("ArxivGateway not provided.")

        # 1. Resolve Collection ID
        collection_id = self.zotero_gateway.get_collection_id_by_name(folder_name)
        if not collection_id:
            raise CollectionNotFoundError(f"Collection '{folder_name}' not found.")

        # 2. Search arXiv
        if verbose:
            print(f"Searching arXiv for: '{query}' (limit: {limit})...")
        
        papers = self.arxiv_gateway.search(query, limit)
        
        success_count = 0
        for paper in papers:
            if verbose:
                print(f"Adding: {paper.title}...")
            
            if self.zotero_gateway.create_item(paper, collection_id):
                success_count += 1
            elif verbose:
                print(f"Failed to add: {paper.title}")
                
        return success_count