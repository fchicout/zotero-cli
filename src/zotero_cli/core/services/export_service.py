import sys
from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import (
    BibliographyFormatter,
    BibtexGateway,
    CollectionRepository,
    RisGateway,
)
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.sdb.sdb_service import SDBService
from zotero_cli.core.zotero_item import ZoteroItem


class ExportService:
    """Service for exporting Zotero items to external formats."""

    def __init__(
        self,
        collection_repo: CollectionRepository,
        bibtex_gateway: BibtexGateway,
        ris_gateway: RisGateway,
        sdb_service: SDBService,
        bibliography_formatter: Optional[BibliographyFormatter] = None,
    ):
        self.collection_repo = collection_repo
        self.bibtex_gateway = bibtex_gateway
        self.ris_gateway = ris_gateway
        self.sdb_service = sdb_service
        self.bibliography_formatter = bibliography_formatter

    def _collection_items(self, collection_name: str) -> Optional[List[ZoteroItem]]:
        col_id = self.collection_repo.get_collection_id_by_name(collection_name)
        if not col_id:
            print(f"Error: Collection '{collection_name}' not found.", file=sys.stderr)
            return None

        items = list(self.collection_repo.get_items_in_collection(col_id))
        if not items:
            print(f"Warning: Collection '{collection_name}' is empty.", file=sys.stderr)
            return None
        return items

    def export_collection(
        self,
        collection_name: str,
        output_path: str,
        format: str = "bibtex",
        style: str = "apa",
        render: str = "plain",
    ) -> bool:
        """
        Exports all items in a collection to a file.
        """
        items = self._collection_items(collection_name)
        if items is None:
            return False
        if format.lower() == "bibliography":
            return self.export_bibliography(items, output_path, style, render)
        return self.export_items(items, output_path, format)

    def collection_bibliography(
        self, collection_name: str, style: str = "apa", render: str = "plain"
    ) -> Optional[str]:
        """A collection as a formatted bibliography; None if missing or empty."""
        items = self._collection_items(collection_name)
        if items is None:
            return None
        return self.serialize_bibliography(items, style, render)

    def export_items(
        self, items: List[ZoteroItem], output_path: str, format: str = "bibtex"
    ) -> bool:
        """
        Exports specific items to a file.
        """
        papers = self._map_items_to_papers(items)

        if not papers:
            print("Warning: No valid papers to export.", file=sys.stderr)
            return False

        if format.lower() == "bibtex":
            return self.bibtex_gateway.write_file(output_path, papers)
        elif format.lower() == "ris":
            return self.ris_gateway.write_file(output_path, papers)
        else:
            print(f"Error: Unsupported export format '{format}'.", file=sys.stderr)
            return False

    def serialize_bibtex(self, items: List[ZoteroItem]) -> str:
        """Serialize items to BibTeX string."""
        papers = self._map_items_to_papers(items)
        return self.bibtex_gateway.serialize(papers) if papers else ""

    def serialize_bibliography(
        self, items: List[ZoteroItem], style: str = "apa", render: str = "plain"
    ) -> str:
        """Serialize items as a formatted bibliography (Issue #534)."""
        if self.bibliography_formatter is None:
            raise RuntimeError("No bibliography formatter configured.")
        bibtex = self.serialize_bibtex(items)
        return self.bibliography_formatter.format(bibtex, style, render) if bibtex else ""

    def export_bibliography(
        self,
        items: List[ZoteroItem],
        output_path: str,
        style: str = "apa",
        render: str = "plain",
    ) -> bool:
        """Write the formatted bibliography to a file."""
        text = self.serialize_bibliography(items, style, render)
        if not text:
            print("Warning: No valid papers to export.", file=sys.stderr)
            return False
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(text if text.endswith("\n") else text + "\n")
        return True

    def serialize_ris(self, items: List[ZoteroItem]) -> str:
        """Serialize items to RIS string."""
        papers = self._map_items_to_papers(items)
        return self.ris_gateway.serialize(papers) if papers else ""

    def _map_items_to_papers(self, items: List[ZoteroItem]) -> List[ResearchPaper]:
        """The exportable items as papers, with the SDB data of all of them
        read together: one request per item made a 12.3k-item export
        12,340 requests (Issue #431)."""
        papers = [i for i in items if i.item_type not in ["attachment", "note"]]
        sdb = self.sdb_service.inspect_items_sdb([i.key for i in papers])
        return [self._map_item_to_paper(i, sdb.get(i.key, [])) for i in papers]

    def _map_item_to_paper(
        self, item: ZoteroItem, sdb_entries: Optional[List[Dict[str, Any]]] = None
    ) -> ResearchPaper:
        """Convert ZoteroItem to ResearchPaper for export."""
        year = None
        if item.date:
            import re

            match = re.search(r"(\d{4})", item.date)
            if match:
                year = match.group(1)

        publication = item.raw_data.get("data", {}).get("publicationTitle")
        if sdb_entries is None:
            sdb_entries = self.sdb_service.inspect_item_sdb(item.key)

        return ResearchPaper(
            title=item.title or "No Title",
            abstract=item.abstract or "",
            key=item.key,
            authors=item.authors,
            year=year,
            publication=publication,
            doi=item.doi,
            url=item.url,
            arxiv_id=item.arxiv_id,
            extra=item.raw_data.get("data", {}).get("extra"),
            sdb_metadata=sdb_entries,
        )
