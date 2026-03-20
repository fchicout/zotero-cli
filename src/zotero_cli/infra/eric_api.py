import logging
from typing import Any, Dict, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

class ERICAPIClient(BaseAPIClient, MetadataProvider):
    def __init__(self):
        # ERIC base URL (IES)
        base_url = "https://api.ies.ed.gov/eric"
        super().__init__(base_url=base_url)

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata for the given identifier (ERIC Accession Number).
        Supports lookups like EJxxxxxx or EDxxxxxx.
        """
        # Validate ERIC ID format (EJ or ED followed by digits)
        if not (identifier.lower().startswith("ej") or identifier.lower().startswith("ed")):
            return None

        try:
            params = {
                "search": f"id:{identifier}",
                "format": "json"
            }

            response = self._get(params=params)
            data = response.json()

            # ERIC returns a list of results in 'response' -> 'docs'
            results = data.get("response", {}).get("docs", [])
            if not results:
                return None

            return self._map_to_research_paper(results[0])

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"Error fetching ERIC metadata for {identifier}: {e}")
            return None
        except Exception as e:
            print(f"Error parsing ERIC response for {identifier}: {e}")
            return None

    def _map_to_research_paper(self, item: Dict[str, Any]) -> ResearchPaper:
        # Title
        title = item.get("title") or ""

        # Abstract
        abstract = item.get("description") or ""

        # Authors
        authors = item.get("author") or []
        if isinstance(authors, str):
            authors = [authors]

        # Publication
        source = item.get("source") or ""

        # Year
        year = str(item.get("pubyear")) if item.get("pubyear") else None

        # DOI
        doi = item.get("doi")

        # Peer Reviewed & Subjects
        extra_parts = []
        if item.get("peerreviewed") == "T":
            extra_parts.append("Peer Reviewed: Yes")

        subjects = item.get("subject") or []
        if isinstance(subjects, str):
            subjects = [subjects]

        if subjects:
            extra_parts.append(f"Subjects: {', '.join(subjects)}")

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=source,
            year=year,
            doi=doi,
            url=f"https://eric.ed.gov/?id={item.get('id')}" if item.get('id') else None,
            extra="\n".join(extra_parts) if extra_parts else None
        )
