import csv
from typing import Iterator

from zotero_cli.core.interfaces import CanonicalCsvGateway
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.utils.csv_safety import sanitize_csv_row, unsanitize_csv_cell


class CanonicalCsvLibGateway(CanonicalCsvGateway):
    """
    Gateway for reading/writing the Zotero-CLI Canonical CSV format.
    Headers: title, doi, arxiv_id, abstract, authors, year, publication, url
    """

    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle semicolon-separated authors
                authors_raw = row.get("authors", "")
                authors = [a.strip() for a in authors_raw.split(";")] if authors_raw else []

                # Issue #237: undo the leading `'` sanitize_csv_row may
                # have added on write, so re-importing a file this
                # project itself exported doesn't treat that marker as
                # literal data.
                yield ResearchPaper(
                    title=str(unsanitize_csv_cell(row.get("title") or "")),
                    doi=row.get("doi"),
                    arxiv_id=row.get("arxiv_id"),
                    abstract=str(unsanitize_csv_cell(row.get("abstract") or "")),
                    authors=[unsanitize_csv_cell(a) for a in authors],
                    year=row.get("year"),
                    publication=unsanitize_csv_cell(row.get("publication")),
                    url=unsanitize_csv_cell(row.get("url")),
                )

    def write_file(self, papers: Iterator[ResearchPaper], file_path: str) -> None:
        headers = ["title", "doi", "arxiv_id", "abstract", "authors", "year", "publication", "url"]
        with open(file_path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for p in papers:
                # Issue #237: title/abstract/authors/etc. can originate
                # from a third-party metadata provider or a Zotero item
                # field - guard against CSV formula injection.
                writer.writerow(
                    sanitize_csv_row(
                        {
                            "title": p.title,
                            "doi": p.doi,
                            "arxiv_id": p.arxiv_id,
                            "abstract": p.abstract,
                            "authors": "; ".join(p.authors),
                            "year": p.year,
                            "publication": p.publication,
                            "url": p.url,
                        }
                    )
                )
