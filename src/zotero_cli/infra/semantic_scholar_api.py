from typing import Optional
import os
import time
import requests
from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

class SemanticScholarAPIClient(BaseAPIClient, MetadataProvider):
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(base_url="https://api.semanticscholar.org/graph/v1/paper")
        self.api_key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        if self.api_key:
            self.session.headers['x-api-key'] = self.api_key

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

        # Fields to retrieve
        fields = "title,abstract,authors,year,venue,externalIds,url,references.externalIds"
        
        # Rate limiting: 1 request per second (keeping it polite)
        time.sleep(1.1)

        try:
            response = self._get(endpoint=s2_id, params={'fields': fields})
            
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

    def _map_to_research_paper(self, data: dict) -> ResearchPaper:
        # Extract authors
        authors = [a['name'] for a in data.get('authors', []) if 'name' in a]
        
        # Extract Identifiers
        external_ids = data.get('externalIds', {})
        doi = external_ids.get('DOI')
        arxiv_id = external_ids.get('ArXiv')
        
        # Extract References (DOIs only for now)
        references = []
        for ref in (data.get('references') or []):
            if ref.get('externalIds') and 'DOI' in ref['externalIds']:
                references.append(ref['externalIds']['DOI'])

        return ResearchPaper(
            title=data.get('title', ''),
            abstract=data.get('abstract', ''),
            arxiv_id=arxiv_id,
            authors=authors,
            publication=data.get('venue', ''),
            year=str(data.get('year')) if data.get('year') else None,
            doi=doi,
            url=data.get('url'),
            references=references,
            citation_count=len(references) # Approximate based on fetched refs
        )