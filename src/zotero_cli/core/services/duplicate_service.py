import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from zotero_cli.core.interfaces import CollectionRepository
from zotero_cli.core.zotero_item import ZoteroItem


@dataclass
class DuplicateGroup:
    # A string representing the identifier that caused the duplication (e.g., "DOI: 10.xxxx" or "Title: My Paper")
    identifier_key: str
    items: List[ZoteroItem] = field(default_factory=list)


class DuplicateFinder:
    """
    Finder service to detect duplicate research items across different collections.
    Supports matching items by DOI, ArXiv ID, or normalized title.
    """

    def __init__(self, gateway: CollectionRepository):
        """
        Initializes the DuplicateFinder with a Zotero gateway.
        """
        self.gateway = gateway

    def find_duplicates(self, collection_ids: List[str]) -> List[dict]:
        """
        Analyzes the specified collections to find duplicate Zotero items.
        Returns a list of dictionaries detailing the duplicate items found.
        """
        all_items_by_identifier: Dict[Tuple[str, str], List[ZoteroItem]] = defaultdict(list)

        for col_id in collection_ids:
            for item in self._fetch_collection_items(col_id):
                identifier = self._identifier_for(item)
                if identifier:
                    all_items_by_identifier[identifier].append(item)

        duplicates = []
        for (id_type, identifier_value), items in all_items_by_identifier.items():
            if len(items) > 1:
                duplicates.append(
                    {"title": items[0].title, "doi": items[0].doi, "keys": [i.key for i in items]}
                )
        return duplicates

    def compare_collections(self, collection_ids: List[str]) -> List[dict]:
        """
        Like `find_duplicates`, but preserves which collection each duplicate
        occurrence came from, for read-only cross-collection duplicate reports
        (e.g. `report duplicates`) that need to show provenance rather than
        just a pooled list of keys.
        """
        all_items_by_identifier: Dict[Tuple[str, str], List[Tuple[ZoteroItem, str]]] = defaultdict(
            list
        )

        for col_id in collection_ids:
            for item in self._fetch_collection_items(col_id):
                identifier = self._identifier_for(item)
                if identifier:
                    all_items_by_identifier[identifier].append((item, col_id))

        duplicates = []
        for (id_type, identifier_value), occurrences in all_items_by_identifier.items():
            if len(occurrences) > 1:
                duplicates.append(
                    {
                        "match_type": id_type,
                        "identifier": identifier_value,
                        "occurrences": [
                            {"key": item.key, "collection_id": col_id, "title": item.title}
                            for item, col_id in occurrences
                        ],
                    }
                )
        return duplicates

    def _fetch_collection_items(self, col_id: str) -> List[ZoteroItem]:
        # col_id is already expected to be a Zotero Key/ID
        items = list(self.gateway.get_items_in_collection(col_id))
        if not items and not self.gateway.get_collection(col_id):
            print(f"Warning: Collection '{col_id}' not found or empty. Skipping.")
            return []
        return items

    def _identifier_for(self, item: ZoteroItem) -> Optional[Tuple[str, str]]:
        normalized_doi = self._normalize_doi(item.doi) if item.doi else None
        normalized_arxiv = item.arxiv_id.strip().lower() if item.arxiv_id else None
        normalized_title = self._normalize_title(item.title) if item.title else None

        if normalized_doi:
            return ("doi", normalized_doi)
        if normalized_arxiv:
            return ("arxiv", normalized_arxiv)
        if normalized_title:
            return ("title", normalized_title)
        return None

    def _normalize_doi(self, doi: str) -> str:
        return doi.strip().lower()

    def _normalize_title(self, title: str) -> str:
        # Lowercase
        title = title.lower()

        # Decompose unicode characters and remove non-spacing marks (accents)
        normalized_title = unicodedata.normalize("NFD", title)
        title = "".join(c for c in normalized_title if unicodedata.category(c) != "Mn")

        # Remove punctuation
        title = re.sub(r"[^\w\s]", "", title)

        # Replace multiple spaces with single space and strip
        title = re.sub(r"\s+", " ", title).strip()

        return title
