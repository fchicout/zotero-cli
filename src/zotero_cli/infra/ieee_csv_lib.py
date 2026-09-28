import csv
import logging
from typing import Iterator

from zotero_cli.core.exceptions import ImportParseError, NotFound
from zotero_cli.core.interfaces import IeeeCsvGateway
from zotero_cli.core.models import ResearchPaper

logger = logging.getLogger(__name__)


class IeeeCsvLibGateway(IeeeCsvGateway):
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            with open(file_path, "r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    yield self._map_row_to_paper(row)
        except FileNotFoundError as e:
            raise NotFound(f"IEEE CSV file '{file_path}' not found.") from e
        except Exception as e:
            logger.exception("Error parsing IEEE CSV file %s", file_path)
            raise ImportParseError(f"Could not parse IEEE CSV file '{file_path}': {e}") from e

    def _map_row_to_paper(self, row: dict) -> ResearchPaper:
        title = row.get("Document Title", "No Title")
        publication = row.get("Publication Title")
        year = row.get("Publication Year")
        doi = row.get("DOI")
        abstract = row.get("Abstract", "")
        url = row.get("PDF Link")

        authors_str = row.get("Authors", "")
        authors = [a.strip() for a in authors_str.split(";") if a.strip()]

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=year,
            doi=doi,
            url=url,
        )
