import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem


@dataclass
class DuplicateGroup:
    # A string representing the identifier that caused the duplication (e.g., "DOI: 10.xxxx" or "Title: My Paper")
    identifier_key: str
    items: List[ZoteroItem] = field(default_factory=list)

class DuplicateFinder:
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def find_duplicates(self, collection_ids: List[str]) -> List[dict]:
        all_items_by_identifier = defaultdict(list)

        for col_id in collection_ids:
            # col_id is already expected to be a Zotero Key/ID
            items = list(self.gateway.get_items_in_collection(col_id))
            if not items and not self.gateway.get_collection(col_id):
                print(f"Warning: Collection '{col_id}' not found or empty. Skipping.")
                continue

            for item in items:
                normalized_doi = self._normalize_doi(item.doi) if item.doi else None
                normalized_arxiv = item.arxiv_id.strip().lower() if item.arxiv_id else None
                normalized_title = self._normalize_title(item.title) if item.title else None

                if normalized_doi:
                    all_items_by_identifier[("doi", normalized_doi)].append(item)
                elif normalized_arxiv:
                    all_items_by_identifier[("arxiv", normalized_arxiv)].append(item)
                elif normalized_title:
                    all_items_by_identifier[("title", normalized_title)].append(item)

        duplicates = []
        for (id_type, identifier_value), items in all_items_by_identifier.items():
            if len(items) > 1:
                duplicates.append({
                    'title': items[0].title,
                    'doi': items[0].doi,
                    'keys': [i.key for i in items]
                })
        return duplicates

    def _normalize_doi(self, doi: str) -> str:
        return doi.strip().lower()

    def _normalize_title(self, title: str) -> str:
        # Lowercase
        title = title.lower()

        # Decompose unicode characters and remove non-spacing marks (accents)
        normalized_title = unicodedata.normalize('NFD', title)
        title = ''.join(c for c in normalized_title if unicodedata.category(c) != 'Mn')

        # Remove punctuation
        title = re.sub(r'[^\w\s]', '', title)

        # Replace multiple spaces with single space and strip
        title = re.sub(r'\s+', ' ', title).strip()

        return title
