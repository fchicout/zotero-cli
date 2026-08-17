from typing import Any, Dict, Iterator, List, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider, SearchableMetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

# OpenAlex's max results per page (https://api.openalex.org/works?per-page=N)
_MAX_PER_PAGE = 200


class OpenAlexAPIClient(BaseAPIClient, MetadataProvider, SearchableMetadataProvider):
    def __init__(self, email: Optional[str] = None):
        # OpenAlex prefers mailto: parameter for the "Polite Pool"
        base_url = "https://api.openalex.org/works"
        headers = {}
        if email:
            headers["User-Agent"] = f"zotero-cli/1.2.0 (mailto:{email})"

        super().__init__(base_url=base_url, headers=headers)

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves full paper metadata for the given identifier (DOI or OpenAlex ID).
        """
        try:
            # Handle DOI if it starts with https://doi.org/
            clean_id = identifier
            if identifier.startswith("https://doi.org/"):
                clean_id = identifier.replace("https://doi.org/", "")

            # OpenAlex endpoint for DOI is works/https://doi.org/DOI
            # But the BaseAPIClient joins base_url/endpoint.
            # OpenAlex works best if we use the canonical DOI URL as the ID.
            if "/" in clean_id and "." in clean_id:  # Likely a DOI
                endpoint = f"https://doi.org/{clean_id}"
            else:
                endpoint = clean_id

            response = self._get(endpoint=endpoint)
            data = response.json()
            return self._map_to_research_paper(data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"Error fetching metadata from OpenAlex for {identifier}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching metadata from OpenAlex for {identifier}: {e}")
            return None

    def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> Iterator[ResearchPaper]:
        """
        Free-text/topic search via GET /works?search=<query> (Issue #179).
        No API key required. sort_by="relevance" (the default) leaves
        ordering to OpenAlex's own relevance ranking, which only applies
        when a `search` param is present; any other sort_by value sorts by
        publication_date instead.
        """
        base_params: Dict[str, Any] = {"search": query}
        if sort_by != "relevance":
            direction = "asc" if sort_order == "ascending" else "desc"
            base_params["sort"] = f"publication_date:{direction}"

        page = 1
        fetched = 0
        while fetched < max_results:
            params = {
                **base_params,
                "page": page,
                "per-page": min(_MAX_PER_PAGE, max_results - fetched),
            }
            try:
                response = self._get(params=params)
                data = response.json()
            except Exception as e:
                print(f"Error searching OpenAlex for '{query}': {e}")
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

    def _map_to_research_paper(self, data: Dict[str, Any]) -> ResearchPaper:
        # Title
        title = data.get("display_name") or ""

        # Abstract (Reconstruct from inverted index)
        abstract = self._reconstruct_abstract(data.get("abstract_inverted_index"))

        # Authors
        authors = []
        for authorship in data.get("authorships", []):
            author = authorship.get("author", {})
            if author.get("display_name"):
                authors.append(author["display_name"])

        # Publication (Journal)
        publication = ""
        primary_location = data.get("primary_location") or {}
        source = primary_location.get("source") or {}
        if source.get("display_name"):
            publication = source["display_name"]

        # PDF URL
        pdf_url = None
        best_oa_location = data.get("best_oa_location") or {}
        if best_oa_location.get("pdf_url"):
            pdf_url = best_oa_location["pdf_url"]

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=str(data.get("publication_year")) if data.get("publication_year") else None,
            doi=data.get("doi"),
            url=data.get("id"),  # OpenAlex ID is a URL
            pdf_url=pdf_url,
        )

    def _reconstruct_abstract(self, inverted_index: Optional[Dict[str, List[int]]]) -> str:
        """
        OpenAlex stores abstracts as an inverted index for legal reasons.
        We must reconstruct it.
        """
        if not inverted_index:
            return ""

        # Determine the length of the abstract
        max_index = 0
        for indices in inverted_index.values():
            if indices:
                max_index = max(max_index, max(indices))

        # Create a list of words in the correct positions
        word_list = [""] * (max_index + 1)
        for word, indices in inverted_index.items():
            for idx in indices:
                word_list[idx] = word

        return " ".join(word_list)
