from typing import List

from zotero_cli.core.interfaces import BibtexGateway, ZoteroGateway
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.sdb.sdb_service import SDBService
from zotero_cli.core.zotero_item import ZoteroItem


class ExportService:
    """Service for exporting Zotero items to external formats."""

    def __init__(
        self, gateway: ZoteroGateway, bibtex_gateway: BibtexGateway, sdb_service: SDBService
    ):
        self.gateway = gateway
        self.bibtex_gateway = bibtex_gateway
        self.sdb_service = sdb_service

    def export_collection(
        self, collection_name: str, output_path: str, format: str = "bibtex"
    ) -> bool:
        """
        Exports all items in a collection to a file.
        """
        # 1. Resolve collection ID
        col_id = self.gateway.get_collection_id_by_name(collection_name)
        if not col_id:
            print(f"Error: Collection '{collection_name}' not found.")
            return False

        # 2. Fetch items
        items = list(self.gateway.get_items_in_collection(col_id))
        if not items:
            print(f"Warning: Collection '{collection_name}' is empty.")
            return False

        return self.export_items(items, output_path, format)

    def export_items(self, items: List[ZoteroItem], output_path: str, format: str = "bibtex") -> bool:
        """
        Exports specific items to a file.
        """
        # 3. Filter for papers (exclude attachments, notes)
        papers = [
            self._map_item_to_paper(item)
            for item in items
            if item.item_type not in ["attachment", "note"]
        ]

        if not papers:
            print("Warning: No valid papers to export.")
            return False

        # 4. Delegate to gateway
        if format.lower() == "bibtex":
            return self.bibtex_gateway.write_file(output_path, papers)
        else:
            print(f"Error: Unsupported export format '{format}'.")
            return False

    def _map_item_to_paper(self, item: ZoteroItem) -> ResearchPaper:
        """Convert ZoteroItem to ResearchPaper for export."""
        # Extract year from date string (e.g., "2023-01-01" -> "2023")
        year = None
        if item.date:
            import re

            match = re.search(r"(\d{4})", item.date)
            if match:
                year = match.group(1)

        # Map publication
        publication = item.raw_data.get("data", {}).get("publicationTitle")

        # Fetch SDB metadata
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
