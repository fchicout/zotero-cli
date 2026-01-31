import logging
from typing import List, Optional

from zotero_cli.core.interfaces import CollectionRepository, ItemRepository
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.duplicate_service import DuplicateFinder
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.services.snowball_graph import SnowballGraphService

logger = logging.getLogger(__name__)


class SnowballIngestionService:
    """
    Handles the ingestion of accepted snowballing candidates into Zotero.
    """

    STATUS_IMPORTED = "IMPORTED"

    def __init__(
        self,
        graph_service: SnowballGraphService,
        metadata_service: MetadataAggregatorService,
        item_repo: ItemRepository,
        collection_repo: CollectionRepository,
        duplicate_finder: DuplicateFinder,
    ):
        self.graph_service = graph_service
        self.metadata_service = metadata_service
        self.item_repo = item_repo
        self.collection_repo = collection_repo
        self.duplicate_finder = duplicate_finder

    def get_accepted_candidates(self) -> List[dict]:
        """Returns list of graph nodes with status ACCEPTED."""
        accepted = []
        for node_id, data in self.graph_service.graph.nodes(data=True):
            if data.get("status") == SnowballGraphService.STATUS_ACCEPTED:
                node_info = data.copy()
                node_info["doi"] = node_id
                accepted.append(node_info)
        return accepted

    def ingest_candidates(self, target_collection_name: str) -> dict:
        """
        Hydrates, checks for duplicates, and uploads accepted candidates to Zotero.
        """
        stats = {"scanned": 0, "imported": 0, "duplicates": 0, "errors": 0}

        # 1. Resolve collection ID
        col_id = self.collection_repo.get_collection_id_by_name(target_collection_name)
        if not col_id:
            logger.error(f"Target collection '{target_collection_name}' not found.")
            return {"error": f"Collection '{target_collection_name}' not found."}

        candidates = self.get_accepted_candidates()
        stats["scanned"] = len(candidates)

        for cand in candidates:
            doi = cand["doi"]
            logger.info(f"Ingesting candidate: {doi}")

            try:
                # 2. Duplicate Guard
                if self._is_duplicate(doi):
                    logger.info(f"Duplicate found for {doi}. Skipping.")
                    stats["duplicates"] += 1
                    # Even if it's a duplicate in Zotero, we mark it as IMPORTED in our graph
                    self.graph_service.update_status(doi, self.STATUS_IMPORTED)
                    continue

                # 3. Hydration
                paper = self._hydrate_paper(cand)
                if not paper:
                    logger.error(f"Failed to hydrate paper for {doi}")
                    stats["errors"] += 1
                    continue

                # 4. Lineage Injection
                self._inject_lineage(paper, cand)

                # 5. Upload
                if self.item_repo.create_item(paper, col_id):
                    logger.info(f"Successfully imported {doi} to Zotero.")
                    stats["imported"] += 1
                    # 6. State Transition
                    self.graph_service.update_status(doi, self.STATUS_IMPORTED)
                else:
                    logger.error(f"Failed to create Zotero item for {doi}")
                    stats["errors"] += 1

            except Exception as e:
                logger.error(f"Error during ingestion of {doi}: {e}")
                stats["errors"] += 1

        self.graph_service.save_graph()
        return stats

    def _is_duplicate(self, doi: str) -> bool:
        """Checks if the paper already exists in the library."""
        # Use get_items_by_doi
        items = list(self.item_repo.get_items_by_doi(doi))
        # Filter strictly for exact DOI match since search might be fuzzy
        for item in items:
            if item.doi and item.doi.lower() == doi.lower():
                return True
        return False

    def _hydrate_paper(self, cand: dict) -> Optional[ResearchPaper]:
        """Ensures full metadata is available."""
        doi = cand["doi"]
        # Try to get enriched metadata
        enriched = self.metadata_service.get_enriched_metadata(doi)
        if enriched:
            return enriched

        # Fallback to stub
        if cand.get("title"):
            return ResearchPaper(
                title=cand["title"],
                abstract=cand.get("abstract", ""),
                doi=doi,
                authors=[],
                year=str(cand.get("year", "")) if cand.get("year") else None,
            )
        return None

    def _inject_lineage(self, paper: ResearchPaper, cand: dict):
        """Adds audit trail to the extra field."""
        doi = cand["doi"]
        parent_doi = None
        # In a DiGraph, predecessors point to this node (parent -> child)
        predecessors = list(self.graph_service.graph.predecessors(doi))
        if predecessors:
            parent_doi = predecessors[0]

        lineage = []
        if parent_doi:
            lineage.append(f"zotero-cli-snowball-parent: {parent_doi}")

        gen = cand.get("generation", 1)
        lineage.append(f"zotero-cli-snowball-gen: {gen}")

        extra_str = "\n".join(lineage)
        if paper.extra:
            paper.extra = paper.extra + "\n" + extra_str
        else:
            paper.extra = extra_str
