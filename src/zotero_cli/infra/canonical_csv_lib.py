import csv
from typing import Iterator

from zotero_cli.core.models import ResearchPaper


class CanonicalCsvLibGateway:
    """
    Gateway for reading/writing the Zotero-CLI Canonical CSV format.
    Headers: title, doi, arxiv_id, abstract, authors, year, publication, url
    """

    def parse_file(self, file_path: str) -> Iterator[ResearchPaper]:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle semicolon-separated authors
                authors_raw = row.get('authors', '')
                authors = [a.strip() for a in authors_raw.split(';')] if authors_raw else []

                yield ResearchPaper(
                    title=str(row.get('title') or ""),
                    doi=row.get('doi'),
                    arxiv_id=row.get('arxiv_id'),
                    abstract=str(row.get('abstract') or ""),
                    authors=authors,
                    year=row.get('year'),
                    publication=row.get('publication'),
                    url=row.get('url')
                )

    def write_file(self, papers: Iterator[ResearchPaper], file_path: str):
        headers = ["title", "doi", "arxiv_id", "abstract", "authors", "year", "publication", "url"]
        with open(file_path, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for p in papers:
                writer.writerow({
                    "title": p.title,
                    "doi": p.doi,
                    "arxiv_id": p.arxiv_id,
                    "abstract": p.abstract,
                    "authors": "; ".join(p.authors),
                    "year": p.year,
                    "publication": p.publication,
                    "url": p.url
                })
