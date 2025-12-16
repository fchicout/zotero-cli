from typing import Optional
from paper2zotero.core.interfaces import ZoteroGateway, ArxivGateway
from paper2zotero.core.models import ResearchPaper

class CollectionNotFoundError(Exception):
    """Raised when the specified Zotero collection cannot be found or created."""
    pass

class PaperImporterClient:
    def __init__(self, zotero_gateway: ZoteroGateway, arxiv_gateway: Optional[ArxivGateway] = None):
        self.zotero_gateway = zotero_gateway
        self.arxiv_gateway = arxiv_gateway

    def _get_or_create_collection(self, folder_name: str) -> str:
        """Helper to get a collection ID or create it if missing."""
        collection_id = self.zotero_gateway.get_collection_id_by_name(folder_name)
        if not collection_id:
            print(f"Collection '{folder_name}' not found. Creating it...")
            collection_id = self.zotero_gateway.create_collection(folder_name)
            if not collection_id:
                raise CollectionNotFoundError(f"Could not create collection '{folder_name}'.")
        return collection_id

    def add_paper(self, arxiv_id: str, abstract: str, title: str, folder_name: str) -> bool:
        """
        Adds a single paper to a Zotero collection.
        """
        # 1. Resolve or Create Collection ID
        collection_id = self._get_or_create_collection(folder_name)

        # 2. Create Domain Model
        paper = ResearchPaper(arxiv_id=arxiv_id, title=title, abstract=abstract)

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

        # 1. Resolve or Create Collection ID
        collection_id = self._get_or_create_collection(folder_name)

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

    def remove_attachments_from_folder(self, folder_name: str, verbose: bool = False) -> int:
        """
        Removes all attachment items from a specified Zotero collection.
        Returns the number of deleted attachments.
        """
        collection_id = self.zotero_gateway.get_collection_id_by_name(folder_name)
        if not collection_id:
            raise CollectionNotFoundError(f"Collection '{folder_name}' not found.")

        if verbose:
            print(f"Fetching items from '{folder_name}'...")

        items = self.zotero_gateway.get_items_in_collection(collection_id)
        deleted_count = 0

        for item in items:
            item_key = item['key']
            item_title = item.get('data', {}).get('title', 'Untitled')
            
            children = self.zotero_gateway.get_item_children(item_key)
            for child in children:
                child_data = child.get('data', {})
                if child_data.get('itemType') == 'attachment':
                    child_key = child['key']
                    child_version = child['version']
                    child_title = child_data.get('title', 'Untitled Attachment')
                    
                    if verbose:
                        print(f"Deleting attachment '{child_title}' from '{item_title}'...")
                    
                    if self.zotero_gateway.delete_item(child_key, child_version):
                        deleted_count += 1
                    elif verbose:
                        print(f"Failed to delete attachment {child_key}")

        return deleted_count
