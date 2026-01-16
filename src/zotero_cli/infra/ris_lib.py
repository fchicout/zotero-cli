from typing import Iterator

import rispy

from zotero_cli.core.interfaces import RisGateway
from zotero_cli.core.models import ResearchPaper


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
            return

    def _map_entry_to_paper(self, entry: dict) -> ResearchPaper:
        # rispy maps tags to human-readable keys
        title = entry.get('primary_title') or entry.get('title') or 'No Title'
        abstract = entry.get('abstract', '')
        authors = entry.get('authors', [])
        doi = entry.get('doi')
        publication = entry.get('journal_name') or entry.get('secondary_title')
        year = entry.get('year')
        # urls is a list in rispy
        urls = entry.get('urls', [])
        url = urls[0] if urls else None

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
