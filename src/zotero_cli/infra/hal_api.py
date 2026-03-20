import logging
from typing import Any, Dict, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

class HALAPIClient(BaseAPIClient, MetadataProvider):
    def __init__(self):
        # HAL base URL
        base_url = "https://api.archives-ouvertes.fr/search"
        super().__init__(base_url=base_url)

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata for the given identifier (HAL ID or DOI).
        """
        try:
            # Determine if identifier is a DOI or HAL ID
            query_field = "identifiant_s"
            if "/" in identifier and "." in identifier: # Likely a DOI
                query_field = "doi_s"

            params = {
                "q": f"{query_field}:{identifier}",
                "wt": "json",
                "fl": "title_s,abstract_s,authFullName_s,journalTitle_s,producedDateY_i,doi_s,uri_s,files_s"
            }

            response = self._get(params=params)
            data = response.json()

            # HAL returns docs in 'response' -> 'docs'
            results = data.get("response", {}).get("docs", [])
            if not results:
                return None

            return self._map_to_research_paper(results[0])

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"Error fetching HAL metadata for {identifier}: {e}")
            return None
        except Exception as e:
            print(f"Error parsing HAL response for {identifier}: {e}")
            return None

    def _map_to_research_paper(self, item: Dict[str, Any]) -> ResearchPaper:
        # Title (list, take first)
        titles = item.get("title_s", [])
        title = titles[0] if titles else ""

        # Abstract (list, take first)
        abstracts = item.get("abstract_s", [])
        abstract = abstracts[0] if abstracts else ""

        # Authors
        authors = item.get("authFullName_s", [])

        # Publication
        journal = item.get("journalTitle_s") or ""

        # Year
        year = str(item.get("producedDateY_i")) if item.get("producedDateY_i") else None

        # DOI (list, take first)
        dois = item.get("doi_s", [])
        doi = dois[0] if dois else None

        # PDF URL (list, take first)
        files = item.get("files_s", [])
        pdf_url = files[0] if files else None

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=journal,
            year=year,
            doi=doi,
            url=item.get("uri_s"),
            pdf_url=pdf_url
        )
