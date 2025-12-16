import bibtexparser
from typing import Iterator
from paper2zotero.core.interfaces import BibtexGateway
from paper2zotero.core.models import ResearchPaper

class BibtexLibGateway(BibtexGateway):
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            with open(file_path, 'r') as bibtex_file:
                bib_database = bibtexparser.load(bibtex_file)
            
            for entry in bib_database.entries:
                yield self._map_entry_to_paper(entry)
        except Exception as e:
            print(f"Error parsing BibTeX file: {e}")
            return iter([])

    def _map_entry_to_paper(self, entry: dict) -> ResearchPaper:
        # Authors: "Smith, John and Doe, Jane"
        authors_str = entry.get('author', '')
        authors = [a.strip() for a in authors_str.split(' and ')] if authors_str else []
        
        # Publication
        publication = entry.get('journal') or entry.get('journaltitle') or entry.get('booktitle')
        
        # Year
        year = entry.get('year') or entry.get('date')
        
        # URL
        url = entry.get('url') or entry.get('link')

        # Clean title (remove { })
        title = entry.get('title', 'No Title').replace('{', '').replace('}', '')

        return ResearchPaper(
            title=title,
            abstract=entry.get('abstract', ''),
            authors=authors,
            publication=publication,
            year=year,
            doi=entry.get('doi'),
            url=url,
            arxiv_id=entry.get('eprint') if entry.get('archivePrefix', '').lower() == 'arxiv' else None
        )
