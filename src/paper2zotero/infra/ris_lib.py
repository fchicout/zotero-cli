import rispy
from typing import Iterator
from paper2zotero.core.interfaces import RisGateway
from paper2zotero.core.models import ResearchPaper

class RisLibGateway(RisGateway):
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            with open(file_path, 'r', encoding='utf-8') as ris_file:
                # rispy.load accepts a file-like object
                entries = rispy.load(ris_file)
            
            for entry in entries:
                yield self._map_entry_to_paper(entry)
        except Exception as e:
            print(f"Error parsing RIS file: {e}")
            return iter([])

    def _map_entry_to_paper(self, entry: dict) -> ResearchPaper:
        title = entry.get('TI') or entry.get('T1') or 'No Title'
        abstract = entry.get('AB', '')
        authors = entry.get('AU', [])
        doi = entry.get('DO')
        publication = entry.get('JF') or entry.get('JO') or entry.get('T2')
        year = entry.get('PY') or entry.get('YR')
        url = entry.get('UR')

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=year,
            doi=doi,
            url=url
            # RIS format doesn't typically have a direct arxiv_id field
        )