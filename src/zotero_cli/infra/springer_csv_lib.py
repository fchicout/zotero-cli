import csv
from typing import Iterator

from zotero_cli.core.interfaces import SpringerCsvGateway
from zotero_cli.core.models import ResearchPaper


class SpringerCsvLibGateway(SpringerCsvGateway):
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            with open(file_path, 'r', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    yield self._map_row_to_paper(row)
        except FileNotFoundError:
            print(f"Error: Springer CSV file '{file_path}' not found.")
            return iter([])
        except Exception as e:
            print(f"Error parsing Springer CSV file: {e}")
            return iter([])

    def _map_row_to_paper(self, row: dict) -> ResearchPaper:
        title = row.get('Item Title', 'No Title')
        publication = row.get('Publication Title') or row.get('Book Series Title')
        year = row.get('Publication Year')
        doi = row.get('Item DOI')
        url = row.get('URL')

        # Omit authors as per decision, Zotero will resolve via DOI

        return ResearchPaper(
            title=title,
            abstract='', # Springer CSV usually doesn't have abstract in this export format directly
            authors=[],  # Omitted
            publication=publication,
            year=year,
            doi=doi,
            url=url
        )
