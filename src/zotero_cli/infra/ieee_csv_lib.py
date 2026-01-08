import csv
from typing import Iterator
from zotero_cli.core.interfaces import IeeeCsvGateway
from zotero_cli.core.models import ResearchPaper

class IeeeCsvLibGateway(IeeeCsvGateway):
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            with open(file_path, 'r', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    yield self._map_row_to_paper(row)
        except FileNotFoundError:
            print(f"Error: IEEE CSV file '{file_path}' not found.")
            return iter([])
        except Exception as e:
            print(f"Error parsing IEEE CSV file: {e}")
            return iter([])

    def _map_row_to_paper(self, row: dict) -> ResearchPaper:
        title = row.get('Document Title', 'No Title')
        publication = row.get('Publication Title')
        year = row.get('Publication Year')
        doi = row.get('DOI')
        abstract = row.get('Abstract', '')
        url = row.get('PDF Link')
        
        authors_str = row.get('Authors', '')
        authors = [a.strip() for a in authors_str.split(';') if a.strip()]

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=year,
            doi=doi,
            url=url
        )