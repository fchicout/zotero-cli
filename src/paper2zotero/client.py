from typing import Optional
from paper2zotero.core.interfaces import ZoteroGateway, ArxivGateway, BibtexGateway, RisGateway, SpringerCsvGateway, IeeeCsvGateway
from paper2zotero.core.models import ResearchPaper

class CollectionNotFoundError(Exception):
    """Raised when the specified Zotero collection cannot be found or created."""
    pass

class PaperImporterClient:
    def __init__(self, zotero_gateway: ZoteroGateway, arxiv_gateway: Optional[ArxivGateway] = None, bibtex_gateway: Optional[BibtexGateway] = None, ris_gateway: Optional[RisGateway] = None, springer_csv_gateway: Optional[SpringerCsvGateway] = None, ieee_csv_gateway: Optional[IeeeCsvGateway] = None):
        self.zotero_gateway = zotero_gateway
        self.arxiv_gateway = arxiv_gateway
        self.bibtex_gateway = bibtex_gateway
        self.ris_gateway = ris_gateway
        self.springer_csv_gateway = springer_csv_gateway
        self.ieee_csv_gateway = ieee_csv_gateway

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

    def import_from_bibtex(self, file_path: str, folder_name: str, verbose: bool = False) -> int:
        """
        Parses a BibTeX file and imports entries into Zotero.
        Returns the number of successfully imported items.
        """
        if not self.bibtex_gateway:
            raise ValueError("BibtexGateway not provided.")

        # 1. Resolve or Create Collection ID
        collection_id = self._get_or_create_collection(folder_name)

        # 2. Parse BibTeX
        if verbose:
            print(f"Parsing BibTeX file: '{file_path}'...")
        
        papers = self.bibtex_gateway.parse_file(file_path)
        
        success_count = 0
        for paper in papers:
            if verbose:
                print(f"Adding: {paper.title}...")
            
            if self.zotero_gateway.create_item(paper, collection_id):
                success_count += 1
            elif verbose:
                print(f"Failed to add: {paper.title}")
                
        return success_count

    def import_from_ris(self, file_path: str, folder_name: str, verbose: bool = False) -> int:
        """
        Parses a RIS file and imports entries into Zotero.
        Returns the number of successfully imported items.
        """
        if not self.ris_gateway:
            raise ValueError("RisGateway not provided.")

        # 1. Resolve or Create Collection ID
        collection_id = self._get_or_create_collection(folder_name)

        # 2. Parse RIS
        if verbose:
            print(f"Parsing RIS file: '{file_path}'...")
        
        papers = self.ris_gateway.parse_file(file_path)
        
        success_count = 0
        for paper in papers:
            if verbose:
                print(f"Adding: {paper.title}...")
            
            if self.zotero_gateway.create_item(paper, collection_id):
                success_count += 1
            elif verbose:
                print(f"Failed to add: {paper.title}")
                
        return success_count

    def import_from_springer_csv(self, file_path: str, folder_name: str, verbose: bool = False) -> int:
        """
        Parses a Springer CSV file and imports entries into Zotero.
        Returns the number of successfully imported items.
        """
        if not self.springer_csv_gateway:
            raise ValueError("SpringerCsvGateway not provided.")

        # 1. Resolve or Create Collection ID
        collection_id = self._get_or_create_collection(folder_name)

        # 2. Parse CSV
        if verbose:
            print(f"Parsing Springer CSV file: '{file_path}'...")
        
        papers = self.springer_csv_gateway.parse_file(file_path)
        
        success_count = 0
        for paper in papers:
            if verbose:
                print(f"Adding: {paper.title}...")
            
            if self.zotero_gateway.create_item(paper, collection_id):
                success_count += 1
            elif verbose:
                print(f"Failed to add: {paper.title}")
                
        return success_count
        
    def import_from_ieee_csv(self, file_path: str, folder_name: str, verbose: bool = False) -> int:
        """
        Parses an IEEE CSV file and imports entries into Zotero.
        Returns the number of successfully imported items.
        """
        if not self.ieee_csv_gateway:
            raise ValueError("IeeeCsvGateway not provided.")

        # 1. Resolve or Create Collection ID
        collection_id = self._get_or_create_collection(folder_name)

        # 2. Parse CSV
        if verbose:
            print(f"Parsing IEEE CSV file: '{file_path}'...")
        
        papers = self.ieee_csv_gateway.parse_file(file_path)
        
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
        
        item_count = 0
        for item in items:
            item_count += 1
            if verbose and item_count % 10 == 0:
                print(f"Processed {item_count} items...", end='\r')

            item_key = item.key
            item_title = item.title if item.title else 'Untitled'
            
            children = self.zotero_gateway.get_item_children(item_key)
            # if verbose and children:
            #    print(f"Item '{item_title}' has {len(children)} children.")

            for child in children:
                child_data = child.get('data', {})
                if child_data.get('itemType') == 'attachment':
                    child_key = child['key']
                    child_version = child.get('version')
                    child_title = child_data.get('title', 'Untitled Attachment')
                    
                    if verbose:
                        print(f"Deleting attachment '{child_title}' from '{item_title}'...")
                    
                    if self.zotero_gateway.delete_item(child_key, child_version):
                        deleted_count += 1
                    elif verbose:
                        print(f"Failed to delete attachment {child_key}")

        return deleted_count
