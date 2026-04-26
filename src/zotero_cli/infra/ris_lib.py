import io
from typing import Iterator, List

import rispy

from zotero_cli.core.interfaces import RisGateway
from zotero_cli.core.models import ResearchPaper


class RisLibGateway(RisGateway):
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            with open(file_path, "r", encoding="utf-8") as ris_file:
                entries = rispy.load(ris_file)

            for entry in entries:
                yield self._map_entry_to_paper(entry)
        except Exception as e:
            print(f"Error parsing RIS file: {e}")
            return

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
            print(f"Error writing RIS file: {e}")
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
