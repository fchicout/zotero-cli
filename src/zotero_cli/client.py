from typing import Any, Optional

from zotero_cli.core.interfaces import (
    ArxivGateway,
    BibtexGateway,
    IeeeCsvGateway,
    RisGateway,
    SpringerCsvGateway,
    ZoteroGateway,
)
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.strategies import (
    ArxivImportStrategy,
    BibtexImportStrategy,
    IeeeCsvImportStrategy,
    RisImportStrategy,
    SpringerCsvImportStrategy,
)


class CollectionNotFoundError(Exception):
    pass

class PaperImporterClient:
    def __init__(self, zotero_gateway: ZoteroGateway,
                 arxiv_gateway: Optional[ArxivGateway] = None,
                 bibtex_gateway: Optional[BibtexGateway] = None,
                 ris_gateway: Optional[RisGateway] = None,
                 springer_csv_gateway: Optional[SpringerCsvGateway] = None,
                 ieee_csv_gateway: Optional[IeeeCsvGateway] = None,
                 semantic_scholar: Any = None,
                 crossref: Any = None,
                 unpaywall: Any = None,
                 canonical_csv_gateway: Any = None):
        self.zotero_gateway = zotero_gateway
        self.arxiv_gateway = arxiv_gateway
        self.bibtex_gateway = bibtex_gateway
        self.ris_gateway = ris_gateway
        self.springer_csv_gateway = springer_csv_gateway
        self.ieee_csv_gateway = ieee_csv_gateway
        self.semantic_scholar = semantic_scholar
        self.crossref = crossref
        self.unpaywall = unpaywall
        self.canonical_csv_gateway = canonical_csv_gateway

    def _get_or_create_collection(self, folder_name: str) -> str:
        col_id = self.zotero_gateway.get_collection_id_by_name(folder_name)
        if not col_id:
            col_id = self.zotero_gateway.create_collection(folder_name)
        if not col_id:
            raise CollectionNotFoundError(f"Collection '{folder_name}' not found and could not be created.")
        return col_id

    def import_with_strategy(self, strategy, source: str, folder_name: str,
                             verbose: bool = False, **kwargs) -> int:
        """
        Generic import method using a specific strategy.
        """
        collection_id = self._get_or_create_collection(folder_name)

        if verbose:
            print(f"Starting import from source: {source}")

        papers = strategy.fetch_papers(source, **kwargs)

        success_count = 0
        for paper in papers:
            if verbose:
                print(f"Adding: {paper.title}...")

            if self.zotero_gateway.create_item(paper, collection_id):
                success_count += 1
            elif verbose:
                print(f"Failed to add: {paper.title}")

        return success_count

    def add_paper(self, arxiv_id: str, abstract: str, title: str, folder_name: str) -> bool:
        collection_id = self._get_or_create_collection(folder_name)
        paper = ResearchPaper(arxiv_id=arxiv_id, abstract=abstract, title=title)
        return self.zotero_gateway.create_item(paper, collection_id)

    def import_from_query(self, query: str, folder_name: str, limit: int = 100,
                          verbose: bool = False, sort_by: str = "relevance",
                          sort_order: str = "descending") -> int:
        if not self.arxiv_gateway:
            raise ValueError("ArxivGateway not provided.")
        strategy = ArxivImportStrategy(self.arxiv_gateway)
        return self.import_with_strategy(strategy, query, folder_name, verbose,
                                         limit=limit, sort_by=sort_by, sort_order=sort_order)

    def import_from_bibtex(self, file_path: str, folder_name: str,
                           verbose: bool = False) -> int:
        if not self.bibtex_gateway:
            raise ValueError("BibtexGateway not provided.")
        strategy = BibtexImportStrategy(self.bibtex_gateway)
        return self.import_with_strategy(strategy, file_path, folder_name, verbose)

    def import_from_ris(self, file_path: str, folder_name: str,
                        verbose: bool = False) -> int:
        if not self.ris_gateway:
            raise ValueError("RisGateway not provided.")
        strategy = RisImportStrategy(self.ris_gateway)
        return self.import_with_strategy(strategy, file_path, folder_name, verbose)

    def import_from_springer_csv(self, file_path: str, folder_name: str,
                                 verbose: bool = False) -> int:
        if not self.springer_csv_gateway:
            raise ValueError("SpringerCsvGateway not provided.")
        strategy = SpringerCsvImportStrategy(self.springer_csv_gateway)
        return self.import_with_strategy(strategy, file_path, folder_name, verbose)

    def import_from_ieee_csv(self, file_path: str, folder_name: str,
                             verbose: bool = False) -> int:
        if not self.ieee_csv_gateway:
            raise ValueError("IeeeCsvGateway not provided.")
        strategy = IeeeCsvImportStrategy(self.ieee_csv_gateway)
        return self.import_with_strategy(strategy, file_path, folder_name, verbose)

    def remove_attachments_from_folder(self, folder_name: str, verbose: bool = False) -> int:
        col_id = self.zotero_gateway.get_collection_id_by_name(folder_name)
        if not col_id:
            return 0
        items = self.zotero_gateway.get_items_in_collection(col_id)
        count = 0
        for item in items:
            count += self.remove_attachments_from_item(item.key, verbose)
        return count

    def remove_attachments_from_item(self, item_key: str, verbose: bool = False) -> int:
        children = self.zotero_gateway.get_item_children(item_key)
        count = 0
        for child in children:
            if child.get('data', {}).get('itemType') == 'attachment':
                if self.zotero_gateway.delete_item(child['key'], child['version']):
                    count += 1
                    if verbose:
                        print(f"Removed attachment: {child['key']}")
        return count

    def attach_missing_pdfs(self, folder_name: str) -> int:
        from zotero_cli.infra.factory import GatewayFactory
        service = GatewayFactory.get_attachment_service()
        return service.attach_pdfs_to_collection(folder_name)
