import logging
from typing import Any, Dict, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

class DBLPAPIClient(BaseAPIClient, MetadataProvider):
    def __init__(self):
        # DBLP base URL
        base_url = "https://dblp.org/search/publ/api"
        super().__init__(base_url=base_url)

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata for the given identifier (DOI or search query).
        """
        try:
            # DBLP API works with queries.
            params = {
                "q": identifier,
                "format": "json",
                "h": 1 # Just get the best match
            }

            response = self._get(params=params)
            data = response.json()

            # DBLP returns 'result' -> 'hits' -> 'hit'
            hits = data.get("result", {}).get("hits", {}).get("hit", [])
            if not hits:
                return None

            # Map the first hit (metadata is inside 'info' key of the hit)
            return self._map_to_research_paper(hits[0].get("info", {}))

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"Error fetching DBLP metadata for {identifier}: {e}")
            return None
        except Exception as e:
            print(f"Error parsing DBLP response for {identifier}: {e}")
            return None

    def _map_to_research_paper(self, info: Dict[str, Any]) -> ResearchPaper:
        # Title
        title = info.get("title") or ""
        if isinstance(title, str):
            # Clean trailing dot often found in DBLP titles
            title = title.rstrip(".")

        # Authors
        authors = []
        author_data = info.get("authors", {}).get("author", [])
        if isinstance(author_data, dict):
            author_data = [author_data]

        for author in author_data:
            if isinstance(author, dict) and author.get("text"):
                authors.append(author["text"])
            elif isinstance(author, str):
                authors.append(author)

        # DOI
        doi = info.get("doi")

        return ResearchPaper(
            title=title,
            abstract="", # DBLP usually doesn't provide abstracts
            authors=authors,
            publication=info.get("venue") or "",
            year=str(info.get("year")) if info.get("year") else None,
            doi=doi,
            url=info.get("ee") # Electronic Edition (often DOI link or publisher URL)
        )
