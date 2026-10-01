import logging
import sys
from typing import Iterator, List, Optional

import bibtexparser
from bibtexparser.library import Library
from bibtexparser.model import Entry, Field
from bxc.latex import LatexTranslator

from zotero_cli.core.exceptions import ImportParseError, NotFound
from zotero_cli.core.interfaces import BibtexGateway
from zotero_cli.core.models import ResearchPaper

logger = logging.getLogger(__name__)

_LATEX = LatexTranslator()


class BibtexLibGateway(BibtexGateway):
    """
    bibtexparser 2.x (Issue #360): its API replaced 1.x's `BibDatabase`/
    `BibTexWriter`/dict-of-strings entries with `Library`/`Entry`/`Field`
    objects. Checked empirically against 1.x with real files before
    migrating, since the two default field values already matched with no
    customization on either side: neither expands LaTeX escapes nor strips
    a field's own braces (only the entry's outer delimiter), and both
    resolve `@string` macros inline by default. So field-by-field reading
    and writing keeps the same values; only the object shapes change.

    On import, the text fields (title, authors, venue, abstract) go through
    bxc's LaTeX translator (Issue #531), so `M{\\"u}ller` is stored as
    `Müller`. Identifier-like fields (DOI, URL, arXiv ID, year) are left
    exactly as written.
    """

    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            library = bibtexparser.parse_file(file_path)
            for entry in library.entries:
                yield self._map_entry_to_paper(entry)
        except FileNotFoundError as e:
            raise NotFound(f"BibTeX file '{file_path}' not found.") from e
        except Exception as e:
            logger.exception("Error parsing BibTeX file %s", file_path)
            raise ImportParseError(f"Could not parse BibTeX file '{file_path}': {e}") from e

    def serialize(self, papers: List[ResearchPaper]) -> str:
        """Serialize list of papers to a BibTeX string."""
        library = Library()
        for paper in papers:
            library.add(self._map_paper_to_entry(paper))
        return bibtexparser.write_string(library)

    def write_file(self, file_path: str, papers: List[ResearchPaper]) -> bool:
        """Export list of papers to a BibTeX file."""
        try:
            content = self.serialize(papers)
            with open(file_path, "w", encoding="utf-8") as bibtex_file:
                bibtex_file.write(content)
            return True
        except Exception as e:
            print(f"Error writing BibTeX file: {e}", file=sys.stderr)
            logger.exception("Error writing BibTeX file %s", file_path)
            return False

    def _map_entry_to_paper(self, entry: Entry) -> ResearchPaper:
        # Authors: "Smith, John and Doe, Jane"
        authors_str = self._text(entry, "author") or ""
        authors = [a.strip() for a in authors_str.split(" and ")] if authors_str else []

        # Publication
        publication = (
            self._text(entry, "journal")
            or self._text(entry, "journaltitle")
            or self._text(entry, "booktitle")
        )

        # Year
        year = self._field(entry, "year") or self._field(entry, "date")

        # URL
        url = self._field(entry, "url") or self._field(entry, "link")

        # Clean title (remove { })
        title = (self._text(entry, "title") or "No Title").replace("{", "").replace("}", "")

        # ArXiv ID
        arxiv_id = None
        archive_prefix = (
            self._field(entry, "archiveprefix") or self._field(entry, "archivePrefix") or ""
        )
        if archive_prefix.lower() == "arxiv":
            arxiv_id = self._field(entry, "eprint")

        return ResearchPaper(
            title=title,
            abstract=self._text(entry, "abstract") or "",
            authors=authors,
            publication=publication,
            year=year,
            doi=self._field(entry, "doi"),
            url=url,
            arxiv_id=arxiv_id,
        )

    @staticmethod
    def _field(entry: Entry, key: str) -> Optional[str]:
        field = entry.get(key)
        return field.value if field else None

    @classmethod
    def _text(cls, entry: Entry, key: str) -> Optional[str]:
        """A human-readable field with its LaTeX escapes turned into Unicode."""
        value = cls._field(entry, key)
        return _LATEX.safe_latex_to_unicode(value) if value else value

    def _map_paper_to_entry(self, paper: ResearchPaper) -> Entry:
        """Convert ResearchPaper to a bibtexparser 2.x Entry."""
        fields: List[Field] = [
            Field(key="title", value=f"{{{paper.title}}}"),
            Field(key="author", value=" and ".join(paper.authors)),
        ]

        if paper.abstract:
            fields.append(Field(key="abstract", value=paper.abstract))
        if paper.publication:
            fields.append(Field(key="journal", value=paper.publication))
        if paper.year:
            fields.append(Field(key="year", value=str(paper.year)))
        if paper.doi:
            fields.append(Field(key="doi", value=paper.doi))
        if paper.url:
            fields.append(Field(key="url", value=paper.url))
        if paper.arxiv_id:
            fields.append(Field(key="eprint", value=paper.arxiv_id))
            fields.append(Field(key="archivePrefix", value="arXiv"))

        # SDB Metadata Enrichment
        if paper.sdb_metadata:
            # 1. Standard 'note' field for human readability
            sdb_summaries = []
            for sdb in paper.sdb_metadata:
                decision = sdb.get("decision", "N/A").upper()
                persona = sdb.get("persona", "Unknown")
                phase = sdb.get("phase", "Unknown")
                criteria = ", ".join(sdb.get("reason_code", []))
                sdb_summaries.append(f"[{persona}/{phase}] {decision}: {criteria}")

            fields.append(Field(key="note", value=" | ".join(sdb_summaries)))

            # 2. Custom x-sdb-* fields (taking the latest/first for simplicity in flat BibTeX)
            # If multiple exist, we suffix with index for full traceability
            for i, sdb in enumerate(paper.sdb_metadata):
                suffix = "" if i == 0 else f"_{i + 1}"
                fields.append(Field(key=f"x-sdb-decision{suffix}", value=sdb.get("decision", "")))
                fields.append(Field(key=f"x-sdb-reviewer{suffix}", value=sdb.get("persona", "")))
                fields.append(Field(key=f"x-sdb-reason{suffix}", value=sdb.get("reason_text", "")))
                fields.append(
                    Field(
                        key=f"x-sdb-criteria{suffix}",
                        value=", ".join(sdb.get("reason_code", [])),
                    )
                )
                fields.append(Field(key=f"x-sdb-evidence{suffix}", value=sdb.get("evidence", "")))
                fields.append(Field(key=f"x-sdb-phase{suffix}", value=sdb.get("phase", "")))

        return Entry(
            entry_type="article",  # Default to article
            key=paper.key or f"item_{id(paper)}",
            fields=fields,
        )
