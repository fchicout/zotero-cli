import io
import logging
from typing import Iterator, List

import rispy

from zotero_cli.core.exceptions import ImportParseError, NotFound
from zotero_cli.core.interfaces import RisGateway
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.utils.notify import NotifyMixin

logger = logging.getLogger(__name__)


class RisLibGateway(RisGateway, NotifyMixin):
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            with open(file_path, "r", encoding="utf-8") as ris_file:
                entries = rispy.load(ris_file)

            for entry in entries:
                yield self._map_entry_to_paper(entry)
        except FileNotFoundError as e:
            raise NotFound(f"RIS file '{file_path}' not found.") from e
        except Exception as e:
            logger.exception("Error parsing RIS file %s", file_path)
            raise ImportParseError(f"Could not parse RIS file '{file_path}': {e}") from e

    def serialize(self, papers: List[ResearchPaper]) -> str:
        """Serialize list of papers to a RIS string."""
        entries = [self._map_paper_to_entry(p) for p in papers]
        output = io.StringIO()
        rispy.dump(entries, output)
        return output.getvalue()

    def write_file(self, file_path: str, papers: List[ResearchPaper]) -> bool:
        """Export list of papers to a RIS file."""
        entries = [self._map_paper_to_entry(p) for p in papers]
        try:
            with open(file_path, "w", encoding="utf-8") as ris_file:
                rispy.dump(entries, ris_file)
            return True
        except Exception as e:
            self._say(f"Error writing RIS file: {e}", logging.ERROR)
            logger.exception("Error writing RIS file %s", file_path)
            return False

    def _map_entry_to_paper(self, entry: dict) -> ResearchPaper:
        title = entry.get("primary_title") or entry.get("title") or "No Title"
        abstract = entry.get("abstract", "")
        authors = entry.get("authors", [])
        doi = entry.get("doi")
        publication = entry.get("journal_name") or entry.get("secondary_title")
        year = entry.get("year")
        urls = entry.get("urls", [])
        url = urls[0] if urls else None

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=year,
            doi=doi,
            url=url,
        )

    def _map_paper_to_entry(self, paper: ResearchPaper) -> dict:
        """Convert ResearchPaper to RIS entry dict."""
        entry = {
            "type_of_reference": "JOUR",  # Default to journal
            "title": paper.title,
            "authors": paper.authors,
        }

        if paper.abstract:
            entry["abstract"] = paper.abstract
        if paper.publication:
            entry["journal_name"] = paper.publication
        if paper.year:
            entry["year"] = str(paper.year)
        if paper.doi:
            entry["doi"] = paper.doi
        if paper.url:
            entry["urls"] = [paper.url]

        return entry
