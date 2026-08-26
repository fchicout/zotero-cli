import logging
import urllib.parse
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

# DOAJ's search endpoint's max results per page (doaj.org/api/v2/docs).
_MAX_PER_PAGE = 100


class DOAJAPIClient(BaseAPIClient, MetadataProvider, SearchableMetadataProvider, CountableMetadataProvider):
    """
    Client for the Directory of Open Access Journals (doaj.org) search API.
    No API key required (Issue #190).
    """

    def __init__(self) -> None:
        super().__init__(base_url="https://doaj.org/api/v2/search/articles")

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves article metadata from DOAJ. DOAJ's search API has no
        dedicated by-ID lookup endpoint, so - same approach as BDTD's
        get_paper_metadata for DOIs/handle URLs - this searches for the
        identifier (typically a DOI) as free text and takes the best match.
        """
        try:
            data = self._search_page(identifier, page=1, page_size=1)
            results = data.get("results", [])
            if not results:
                return None
            return self._map_to_research_paper(results[0])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            logger.exception(f"DOAJAPIClient: Error fetching metadata for {identifier}")
            return None
        except Exception:
            logger.exception(f"DOAJAPIClient: Error fetching metadata for {identifier}")
            return None

    def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> Iterator[ResearchPaper]:
        """
        Free-text/topic search via DOAJ's search API (Issue #190).
        sort_by/sort_order are accepted for interface parity with
        ArxivGateway.search/SearchableMetadataProvider but not honored -
        DOAJ's search endpoint doesn't expose a documented sort override
        beyond its own relevance ranking.
        """
        page = 1
        fetched = 0
        while fetched < max_results:
            page_size = min(_MAX_PER_PAGE, max_results - fetched)
            try:
                data = self._search_page(query, page=page, page_size=page_size)
            except Exception:
                logger.exception(f"DOAJAPIClient: Error searching for '{query}'")
                return

            results = data.get("results", [])
            if not results:
                return

            for item in results:
                yield self._map_to_research_paper(item)
                fetched += 1
                if fetched >= max_results:
                    return

            page += 1

    def count(self, query: str) -> int:
        """
        Returns the total result count for a query without fetching full
        article records (Issue #190) - requests a single-item page and
        reads the same `total` field search() already paginates against.
        """
        try:
            data = self._search_page(query, page=1, page_size=1)
        except Exception:
            logger.exception(f"DOAJAPIClient: Error counting results for '{query}'")
            return 0
        return int(data.get("total", 0))

    def _search_page(self, query: str, page: int, page_size: int) -> Dict[str, Any]:
        # DOAJ's search endpoint embeds the query in the URL path, not a
        # query-string param.
        encoded_query = urllib.parse.quote(query, safe="")
        response = self._get(
            endpoint=encoded_query,
            params={"page": page, "pageSize": page_size},
        )
        return dict(response.json())

    def _map_to_research_paper(self, item: Dict[str, Any]) -> ResearchPaper:
        bibjson = item.get("bibjson", {})

        title = bibjson.get("title") or ""
        abstract = bibjson.get("abstract") or ""

        authors: List[str] = [
            str(a["name"])
            for a in bibjson.get("author", [])
            if isinstance(a, dict) and a.get("name")
        ]

        year = str(bibjson.get("year")) if bibjson.get("year") else None

        journal = bibjson.get("journal") or {}
        publication = journal.get("title")

        doi = None
        for identifier in bibjson.get("identifier", []):
            if identifier.get("type", "").lower() == "doi":
                doi = identifier.get("id")
                break

        url = None
        for link in bibjson.get("link", []):
            if link.get("type") == "fulltext":
                url = link.get("url")
                break

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=year,
            doi=doi,
            url=url,
        )
