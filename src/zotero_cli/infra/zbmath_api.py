import logging
from typing import Any, Dict, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

class zbMATHAPIClient(BaseAPIClient, MetadataProvider):
    def __init__(self):
        # zbMATH base URL
        base_url = "https://api.zbmath.org/v1"
        super().__init__(base_url=base_url)

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata for the given identifier (Zbl Number or DOI).
        """
        try:
            # zbMATH API works with queries.
            # DOI lookup: q=doi:10.1007/s00209-020-02612-w
            # Zbl lookup: q=an:1453.14001

            query = identifier
            if "/" in identifier and "." in identifier: # Likely a DOI
                query = f"doi:{identifier}"
            elif identifier.startswith("zbl") or identifier.replace(".", "").isdigit():
                # Simple heuristic for Zbl number
                query = f"an:{identifier}"

            params = {
                "q": query,
                "fmt": "json"
            }

            response = self._get(endpoint="software" if "sw" in identifier.lower() else "document", params=params)
            data = response.json()

            results = data.get("results", [])
            if not results:
                # Try documents endpoint if it wasn't used
                if "sw" not in identifier.lower():
                    # Already tried documents
                    return None
                return None

            # zbMATH returns a list of results, we take the first one
            return self._map_to_research_paper(results[0])

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"Error fetching zbMATH metadata for {identifier}: {e}")
            return None
        except Exception as e:
            print(f"Error parsing zbMATH response for {identifier}: {e}")
            return None

    def _map_to_research_paper(self, item: Dict[str, Any]) -> ResearchPaper:
        # Title
        title = item.get("title") or ""

        # Abstract (Reviews in zbMATH)
        abstract = item.get("review") or ""

        # Authors
        authors = []
        author_list = item.get("authors", [])
        for author in author_list:
            if isinstance(author, dict) and author.get("name"):
                authors.append(author["name"])
            elif isinstance(author, str):
                authors.append(author)

        # Publication
        source = item.get("source") or ""

        # Year
        year = str(item.get("year")) if item.get("year") else None

        # DOI
        doi = item.get("doi")

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=source,
            year=year,
            doi=doi,
            url=f"https://zbmath.org/?q=an:{item.get('zbl_id')}" if item.get('zbl_id') else None
        )
