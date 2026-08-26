import logging
from typing import Any, Dict, Iterator, List, Optional

import requests

from zotero_cli.core.interfaces import (
    CountableMetadataProvider,
    MetadataProvider,
    SearchableMetadataProvider,
)
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

# CORE's search endpoint's max results per page (api.core.ac.uk/docs/v3).
_MAX_PER_PAGE = 100


class CoreAPIClient(
    BaseAPIClient, MetadataProvider, SearchableMetadataProvider, CountableMetadataProvider
):
    """
    Client for the CORE (core.ac.uk) open-access aggregator's search API v3
    (Issue #190). Requires a free API key (registration at core.ac.uk); the
    free tier is rate-limited to 3,000 requests/month, 3 req/s.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        super().__init__(base_url="https://api.core.ac.uk/v3", headers=headers)
        self.api_key = api_key

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata from CORE. Supports a numeric CORE work ID
        (direct GET /works/{id}) or a DOI (search by `doi:"<doi>"`, taking
        the best match - CORE's v3 API has no separate DOI-lookup endpoint).
        """
        try:
            clean_id = identifier.strip()
            if clean_id.isdigit():
                response = self._get(endpoint=f"works/{clean_id}")
                data = response.json()
                return self._map_to_research_paper(data)

            response = self._get(
                endpoint="search/works",
                params={"q": f'doi:"{clean_id}"', "limit": 1},
            )
            data = response.json()
            results = data.get("results", [])
            if not results:
                return None
            return self._map_to_research_paper(results[0])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"CoreAPIClient: Error fetching metadata for {identifier}: {e}")
            return None
        except Exception as e:
            logger.error(f"CoreAPIClient: Error fetching metadata for {identifier}: {e}")
            return None

    def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> Iterator[ResearchPaper]:
        """
        Free-text/topic search via GET /search/works (Issue #190).
        sort_by/sort_order are accepted for interface parity with
        ArxivGateway.search/SearchableMetadataProvider but not honored -
        CORE's default is relevance ranking, with no documented override
        used here.
        """
        offset = 0
        fetched = 0
        while fetched < max_results:
            limit = min(_MAX_PER_PAGE, max_results - fetched)
            try:
                response = self._get(
                    endpoint="search/works",
                    params={"q": query, "limit": limit, "offset": offset},
                )
                data = response.json()
            except Exception as e:
                logger.error(f"CoreAPIClient: Error searching for '{query}': {e}")
                return

            results = data.get("results", [])
            if not results:
                return

            for item in results:
                yield self._map_to_research_paper(item)
                fetched += 1
                if fetched >= max_results:
                    return

            offset += len(results)

    def count(self, query: str) -> int:
        """
        Returns the total result count for a query without fetching full
        work records (Issue #190) - requests a single-item page and reads
        `totalHits`, the same total search() paginates against.
        """
        try:
            response = self._get(endpoint="search/works", params={"q": query, "limit": 1})
            data = response.json()
        except Exception as e:
            logger.error(f"CoreAPIClient: Error counting results for '{query}': {e}")
            return 0
        return int(data.get("totalHits", 0))

    def _map_to_research_paper(self, item: Dict[str, Any]) -> ResearchPaper:
        title = item.get("title") or ""
        abstract = item.get("abstract") or ""

        authors: List[str] = [
            str(a["name"]) for a in item.get("authors", []) if isinstance(a, dict) and a.get("name")
        ]

        year = str(item.get("yearPublished")) if item.get("yearPublished") else None
        doi = item.get("doi")
        publication = item.get("publisher")
        url = item.get("downloadUrl") or item.get("sourceFulltextUrls", [None])[0]

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=year,
            doi=doi,
            url=url,
            pdf_url=item.get("downloadUrl"),
        )
