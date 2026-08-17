import os
import time
from typing import Any, Dict, Iterator, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider, SearchableMetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

# Semantic Scholar's max results per page for /paper/search
_MAX_PER_PAGE = 100

_SEARCH_FIELDS = (
    "title,abstract,authors,year,venue,externalIds,url,references.externalIds,openAccessPdf"
)


class SemanticScholarAPIClient(BaseAPIClient, MetadataProvider, SearchableMetadataProvider):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(base_url="https://api.semanticscholar.org/graph/v1/paper")
        self.api_key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        if self.api_key:
            self.session.headers["x-api-key"] = self.api_key

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata from Semantic Scholar.
        Identifier can be a DOI, arXiv ID, or S2 Paper ID.
        """
        # Semantic Scholar ID format: DOI:10.xxx or ARXIV:xxxx
        s2_id = identifier
        if "10." in identifier and not identifier.startswith("DOI:"):
            s2_id = f"DOI:{identifier}"
        elif "arxiv" in identifier.lower() and not identifier.upper().startswith("ARXIV:"):
            # Basic handling, might need more robust parsing if identifier is a URL
            pass

        fields = _SEARCH_FIELDS

        # Rate limiting: 1 request per second (keeping it polite)
        time.sleep(1.1)

        try:
            response = self._get(endpoint=s2_id, params={"fields": fields})

            data = response.json()
            return self._map_to_research_paper(data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"Error fetching metadata from Semantic Scholar for {identifier}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching metadata from Semantic Scholar for {identifier}: {e}")
            return None

    def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> Iterator[ResearchPaper]:
        """
        Free-text/topic search via GET /graph/v1/paper/search?query=<query>
        (Issue #179). No API key required (one is still respected if
        configured, same as get_paper_metadata). sort_by/sort_order are
        accepted for interface parity with ArxivGateway.search but not
        honored - the basic search endpoint only offers relevance ordering,
        with no override (Semantic Scholar's bulk-search endpoint supports
        sorting but is a different API shape, out of scope here).
        """
        offset = 0
        fetched = 0
        total: Optional[int] = None

        while fetched < max_results and (total is None or offset < total):
            page_limit = min(_MAX_PER_PAGE, max_results - fetched)
            time.sleep(1.1)  # Rate limiting: 1 request per second (keeping it polite)

            try:
                response = self._get(
                    endpoint="search",
                    params={
                        "query": query,
                        "fields": _SEARCH_FIELDS,
                        "limit": page_limit,
                        "offset": offset,
                    },
                )
                data: Dict[str, Any] = response.json()
            except Exception as e:
                print(f"Error searching Semantic Scholar for '{query}': {e}")
                return

            total = data.get("total", 0)
            papers = data.get("data", [])
            if not papers:
                return

            for item in papers:
                yield self._map_to_research_paper(item)
                fetched += 1
                if fetched >= max_results:
                    return

            offset += len(papers)

    def _map_to_research_paper(self, data: dict) -> ResearchPaper:
        # Extract authors
        authors = [a["name"] for a in data.get("authors", []) if "name" in a]

        # Extract Identifiers
        external_ids = data.get("externalIds", {})
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")

        # Extract PDF URL
        pdf_url = data.get("openAccessPdf", {}).get("url") if data.get("openAccessPdf") else None

        # Extract References (DOIs only for now)
        references = []
        for ref in data.get("references") or []:
            if ref.get("externalIds") and "DOI" in ref["externalIds"]:
                references.append(ref["externalIds"]["DOI"])

        return ResearchPaper(
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            arxiv_id=arxiv_id,
            authors=authors,
            publication=data.get("venue", ""),
            year=str(data.get("year")) if data.get("year") else None,
            doi=doi,
            url=data.get("url"),
            pdf_url=pdf_url,
            references=references,
            citation_count=len(references),  # Approximate based on fetched refs
        )
