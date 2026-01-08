import requests
import os
from typing import Optional
from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper

class UnpaywallAPIClient(MetadataProvider):
    BASE_URL = "https://api.unpaywall.org/v2/"
    
    def __init__(self):
        self.email = os.environ.get("UNPAYWALL_EMAIL", "unpaywall_client@zotero_cli.com")

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves metadata including PDF URL from Unpaywall.
        Identifier should be a DOI.
        """
        # Unpaywall works best with DOIs. If it's not a DOI, return None or try to extract.
        if "10." not in identifier:
            return None
            
        url = f"{self.BASE_URL}{identifier}?email={self.email}"
        
        try:
            response = requests.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            
            data = response.json()
            return self._map_to_research_paper(data)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from Unpaywall for {identifier}: {e}")
            return None

    def _map_to_research_paper(self, data: dict) -> ResearchPaper:
        # Title
        title = data.get('title', '')
        
        # Authors
        authors = []
        for author in data.get('z_authors', []) or []:
            given = author.get('given', '')
            family = author.get('family', '')
            if given or family:
                authors.append(f"{given} {family}".strip())
        
        # Year
        year = str(data.get('year')) if data.get('year') else None
        
        # Publication / Venue
        publication = data.get('publisher', '')
        if not publication:
            publication = data.get('journal_name', '')

        # PDF URL - Unpaywall specific value
        pdf_url = None
        best_oa_location = data.get('best_oa_location', {})
        if best_oa_location:
            pdf_url = best_oa_location.get('url_for_pdf')
        
        # If no PDF in best location, check oa_locations
        if not pdf_url:
            for loc in data.get('oa_locations', []) or []:
                if loc.get('url_for_pdf'):
                    pdf_url = loc.get('url_for_pdf')
                    break

        return ResearchPaper(
            title=title,
            abstract="", # Unpaywall rarely has abstracts
            authors=authors,
            publication=publication,
            year=year,
            doi=data.get('doi'),
            url=data.get('doi_url'),
            pdf_url=pdf_url,
            citation_count=None, # Unpaywall doesn't provide this
            references=[]
        )
