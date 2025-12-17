import requests
from typing import List, Optional
from paper2zotero.core.interfaces import MetadataProvider
from paper2zotero.core.models import ResearchPaper

class CrossRefAPIClient(MetadataProvider):
    BASE_URL = "https://api.crossref.org/works/"

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves full paper metadata (including references) for the given identifier (DOI).
        Returns a ResearchPaper object if found, otherwise None.
        """
        url = f"{self.BASE_URL}{identifier}"
        try:
            response = requests.get(url, headers={'User-Agent': 'paper2zotero/1.0 (mailto:fchicout@gmail.com)'})
            response.raise_for_status()
            data = response.json()
            return self._map_to_research_paper(data)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching metadata for DOI {identifier} from CrossRef: {e}")
            return None

    def _map_to_research_paper(self, data: dict) -> ResearchPaper:
        item = data.get('message', {})
        
        # Title
        title = item.get('title', [''])[0] if item.get('title') else ''
        
        # Abstract (often XML)
        abstract = item.get('abstract', '')
        
        # Authors
        authors = []
        for author in item.get('author', []):
            given = author.get('given', '')
            family = author.get('family', '')
            if given or family:
                authors.append(f"{given} {family}".strip())
        
        # Year
        year = None
        published = item.get('published-print') or item.get('published-online')
        if published and 'date-parts' in published:
            year = str(published['date-parts'][0][0])

        # References
        references = []
        if 'reference' in item:
            for ref in item['reference']:
                if 'DOI' in ref and ref['DOI']:
                    references.append(ref['DOI'])

        return ResearchPaper(
            title=title,
            abstract=abstract, # CrossRef abstract is often XML/HTML
            authors=authors,
            publication=item.get('container-title', [''])[0] if item.get('container-title') else '',
            year=year,
            doi=item.get('DOI'),
            url=item.get('URL'),
            references=references,
            citation_count=item.get('is-referenced-by-count')
        )
