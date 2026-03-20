from typing import Any, Dict, List, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient


class OpenAlexAPIClient(BaseAPIClient, MetadataProvider):
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
            if "/" in clean_id and "." in clean_id: # Likely a DOI
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
            url=data.get("id"), # OpenAlex ID is a URL
            pdf_url=pdf_url
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
