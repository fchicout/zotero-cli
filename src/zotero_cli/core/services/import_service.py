from typing import Iterator

from zotero_cli.core.interfaces import ItemRepository
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.collection_service import CollectionService


class ImportService:
    """
    Service for importing research papers into Zotero collections.
    Handles bulk imports from strategies and targeted manual entries.
    """

    def __init__(self, item_repo: ItemRepository, col_service: CollectionService):
        """
        Initializes the ImportService with item and collection repositories.
        """
        self.item_repo = item_repo
        self.col_service = col_service

    def import_papers(
        self, papers: Iterator[ResearchPaper], collection_name: str, verbose: bool = False
    ) -> int:
        """
        Imports an iterator of research papers into a specified collection.
        Resolves or creates the collection if necessary.
        """
        col_id = self.col_service.get_or_create_collection_id(collection_name)

        success_count = 0
        for paper in papers:
            if verbose:
                doi_info = f" [DOI: {paper.doi}]" if paper.doi else ""
                print(f"Adding: {paper.title}{doi_info}...")

            if self.item_repo.create_item(paper, col_id):
                success_count += 1
            elif verbose:
                print(f"Failed to add: {paper.title}")

        return success_count

    def add_manual_paper(self, paper: ResearchPaper, collection_name: str) -> bool:
        """
        Manually adds a single research paper to a collection.
        """
        col_id = self.col_service.get_or_create_collection_id(collection_name)
        return self.item_repo.create_item(paper, col_id)
