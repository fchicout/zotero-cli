import logging
from typing import Any, Dict, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

class InspireHEPAPIClient(BaseAPIClient, MetadataProvider):
    def __init__(self):
        # INSPIRE-HEP base URL
        base_url = "https://inspirehep.net/api/literature"
        super().__init__(base_url=base_url)

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata for the given identifier (DOI, arXiv ID, or INSPIRE ID).
        """
        try:
            # Determine prefix based on identifier format
            query = identifier
            if "/" in identifier and "." in identifier: # DOI
                query = f"doi {identifier}"
            elif identifier.startswith("hal-"): # HAL ID (skip)
                return None
            elif "." in identifier and (identifier[0].isdigit() or "/" in identifier): # arXiv
                query = f"eprint {identifier}"
            elif identifier.replace(".", "").isdigit(): # Likely INSPIRE ID (recid)
                query = f"recid {identifier}"

            params = {
                "q": query,
                "format": "json"
            }

            response = self._get(params=params)
            data = response.json()

            # INSPIRE returns 'hits' -> 'hits'
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                return None

            # Map the first hit (metadata is inside 'metadata' key of the hit)
            return self._map_to_research_paper(hits[0].get("metadata", {}))

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"Error fetching INSPIRE-HEP metadata for {identifier}: {e}")
            return None
        except Exception as e:
            print(f"Error parsing INSPIRE-HEP response for {identifier}: {e}")
            return None

    def _map_to_research_paper(self, metadata: Dict[str, Any]) -> ResearchPaper:
        # Title
        titles = metadata.get("titles", [])
        title = titles[0].get("title") if titles else ""

        # Abstract
        abstracts = metadata.get("abstracts", [])
        abstract = abstracts[0].get("value") if abstracts else ""

        # Authors
        authors = []
        for author in metadata.get("authors", []):
            if author.get("full_name"):
                authors.append(author["full_name"])

        # Publication info
        pub_info = metadata.get("publication_info", [])
        journal = pub_info[0].get("journal_title") if pub_info else ""
        year = str(pub_info[0].get("year")) if pub_info and pub_info[0].get("year") else None

        # DOI
        dois = metadata.get("dois", [])
        doi = dois[0].get("value") if dois else None

        # arXiv
        arxiv_id = None
        arxiv_list = metadata.get("arxiv_eprints", [])
        if arxiv_list:
            arxiv_id = arxiv_list[0].get("value")

        # Extra HEP fields
        extra_parts = []
        collaborations = metadata.get("collaborations", [])
        if collaborations:
            names = [c.get("value") for c in collaborations if c.get("value")]
            if names:
                extra_parts.append(f"Collaborations: {', '.join(names)}")

        report_numbers = metadata.get("report_numbers", [])
        if report_numbers:
            nums = [r.get("value") for r in report_numbers if r.get("value")]
            if nums:
                extra_parts.append(f"Report Numbers: {', '.join(nums)}")

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=journal,
            year=year,
            doi=doi,
            arxiv_id=arxiv_id,
            url=f"https://inspirehep.net/literature/{metadata.get('control_number')}" if metadata.get('control_number') else None,
            extra="\n".join(extra_parts) if extra_parts else None
        )
