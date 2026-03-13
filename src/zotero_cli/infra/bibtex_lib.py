from typing import Iterator, List

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter

from zotero_cli.core.interfaces import BibtexGateway
from zotero_cli.core.models import ResearchPaper


class BibtexLibGateway(BibtexGateway):
    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        try:
            with open(file_path, "r", encoding="utf-8") as bibtex_file:
                bib_database = bibtexparser.load(bibtex_file)

            for entry in bib_database.entries:
                yield self._map_entry_to_paper(entry)
        except Exception as e:
            print(f"Error parsing BibTeX file: {e}")
            return

    def write_file(self, file_path: str, papers: List[ResearchPaper]) -> bool:
        """Export list of papers to a BibTeX file."""
        db = BibDatabase()
        db.entries = [self._map_paper_to_entry(p) for p in papers]

        writer = BibTexWriter()
        try:
            with open(file_path, "w", encoding="utf-8") as bibtex_file:
                bibtex_file.write(writer.write(db))
            return True
        except Exception as e:
            print(f"Error writing BibTeX file: {e}")
            return False

    def _map_entry_to_paper(self, entry: dict) -> ResearchPaper:
        # Authors: "Smith, John and Doe, Jane"
        authors_str = entry.get("author", "")
        authors = [a.strip() for a in authors_str.split(" and ")] if authors_str else []

        # Publication
        publication = entry.get("journal") or entry.get("journaltitle") or entry.get("booktitle")

        # Year
        year = entry.get("year") or entry.get("date")

        # URL
        url = entry.get("url") or entry.get("link")

        # Clean title (remove { })
        title = entry.get("title", "No Title").replace("{", "").replace("}", "")

        # ArXiv ID
        arxiv_id = None
        if entry.get("archiveprefix", "").lower() == "arxiv":
            arxiv_id = entry.get("eprint")
        elif entry.get("archivePrefix", "").lower() == "arxiv":
            arxiv_id = entry.get("eprint")

        return ResearchPaper(
            title=title,
            abstract=entry.get("abstract", ""),
            authors=authors,
            publication=publication,
            year=year,
            doi=entry.get("doi"),
            url=url,
            arxiv_id=arxiv_id,
        )

    def _map_paper_to_entry(self, paper: ResearchPaper) -> dict:
        """Convert ResearchPaper to BibTeX entry dict."""
        entry = {
            "ID": paper.key or f"item_{id(paper)}",
            "ENTRYTYPE": "article",  # Default to article
            "title": f"{{{paper.title}}}",
            "author": " and ".join(paper.authors),
        }

        if paper.abstract:
            entry["abstract"] = paper.abstract
        if paper.publication:
            entry["journal"] = paper.publication
        if paper.year:
            entry["year"] = str(paper.year)
        if paper.doi:
            entry["doi"] = paper.doi
        if paper.url:
            entry["url"] = paper.url
        if paper.arxiv_id:
            entry["eprint"] = paper.arxiv_id
            entry["archivePrefix"] = "arXiv"

        # SDB Metadata Enrichment
        if paper.sdb_metadata:
            # 1. Standard 'note' field for human readability
            sdb_summaries = []
            for i, sdb in enumerate(paper.sdb_metadata, 1):
                decision = sdb.get("decision", "N/A").upper()
                persona = sdb.get("persona", "Unknown")
                phase = sdb.get("phase", "Unknown")
                criteria = ", ".join(sdb.get("reason_code", []))
                sdb_summaries.append(f"[{persona}/{phase}] {decision}: {criteria}")

            entry["note"] = " | ".join(sdb_summaries)

            # 2. Custom x-sdb-* fields (taking the latest/first for simplicity in flat BibTeX)
            # If multiple exist, we suffix with index for full traceability
            for i, sdb in enumerate(paper.sdb_metadata):
                suffix = "" if i == 0 else f"_{i + 1}"
                entry[f"x-sdb-decision{suffix}"] = sdb.get("decision", "")
                entry[f"x-sdb-reviewer{suffix}"] = sdb.get("persona", "")
                entry[f"x-sdb-reason{suffix}"] = sdb.get("reason_text", "")
                entry[f"x-sdb-criteria{suffix}"] = ", ".join(sdb.get("reason_code", []))
                entry[f"x-sdb-evidence{suffix}"] = sdb.get("evidence", "")
                entry[f"x-sdb-phase{suffix}"] = sdb.get("phase", "")

        return entry
