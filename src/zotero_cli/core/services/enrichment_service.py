import time
from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import ArxivGateway, CollectionRepository, ItemRepository
from zotero_cli.core.zotero_item import ZoteroItem


class EnrichmentService:
    def __init__(
        self,
        item_repo: ItemRepository,
        collection_repo: CollectionRepository,
        arxiv_gateway: ArxivGateway,
    ):
        self.item_repo = item_repo
        self.collection_repo = collection_repo
        self.arxiv_gateway = arxiv_gateway

    def hydrate_item(self, item_key: str, dry_run: bool = False) -> Optional[Dict[str, Any]]:
        """
        Fetches latest metadata for an ArXiv item and updates Zotero if DOI or Journal is found.
        Returns a dict with changes if any, else None.
        """
        item = self.item_repo.get_item(item_key)
        if not item:
            return None

        return self._hydrate_single_item(item, dry_run)

    def hydrate_collection(self, collection_id: str, dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        Hydrates all items in a collection that originate from ArXiv.
        """
        items = self.collection_repo.get_items_in_collection(collection_id)
        results = []

        for item in items:
            # Identity source: check if it's ArXiv
            if self._is_arxiv_item(item):
                change = self._hydrate_single_item(item, dry_run)
                if change:
                    results.append(change)
                # Throttling
                time.sleep(1)

        return results

    def hydrate_all(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        Global ArXiv scan and hydration.
        """
        from zotero_cli.core.models import ZoteroQuery

        # Search for items where libraryCatalog contains ArXiv or URL contains arxiv.org
        # Note: Zotero API search is somewhat limited, so we do a general search and filter client-side.
        query = ZoteroQuery(q="arxiv.org")

        # We need the full gateway to access search_items
        # Since we might only have ItemRepository interface, we check or cast if needed.
        # But in our factory, we pass the Gateway.
        if not hasattr(self.item_repo, "search_items"):
            print("Error: Underlying repository does not support global search.")
            return []

        # Use type check or casting to access search_items on the gateway
        search_func = getattr(self.item_repo, "search_items")
        items = search_func(query)
        results = []

        for item in items:
            if self._is_arxiv_item(item):
                change = self._hydrate_single_item(item, dry_run)
                if change:
                    results.append(change)
                # Throttling
                time.sleep(1)

        return results

    def _is_arxiv_item(self, item: ZoteroItem) -> bool:
        catalog = item.raw_data.get("data", {}).get("libraryCatalog", "").lower()
        if "arxiv" in catalog:
            return True
        if item.url and "arxiv.org" in item.url:
            return True
        if item.arxiv_id:
            return True
        return False

    def _hydrate_single_item(
        self, item: ZoteroItem, dry_run: bool = False
    ) -> Optional[Dict[str, Any]]:
        arxiv_id = item.arxiv_id
        if not arxiv_id:
            return None

        # Query ArXiv
        papers = list(self.arxiv_gateway.search(f"id:{arxiv_id}", max_results=1))
        if not papers:
            return None

        latest = papers[0]
        changes = {}

        # 1. Check DOI
        if not item.doi and latest.doi:
            changes["DOI"] = latest.doi

        # 2. Check Journal
        current_journal = item.raw_data.get("data", {}).get("publicationTitle", "")
        if not current_journal and latest.publication:
            changes["publicationTitle"] = latest.publication

        if not changes:
            return None

        report = {
            "key": item.key,
            "title": item.title or "Unknown Title",
            "old_doi": item.doi or "N/A",
            "new_doi": latest.doi or "N/A",
            "old_journal": current_journal or "N/A",
            "new_journal": latest.publication or "N/A",
        }

        if not dry_run:
            success = self.item_repo.update_item(item.key, item.version, changes)
            if not success:
                print(f"Failed to update item {item.key}")
                return None

        return report
