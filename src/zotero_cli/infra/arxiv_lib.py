import re
from typing import Iterator

import arxiv

from zotero_cli.core.interfaces import ArxivGateway
from zotero_cli.core.models import ResearchPaper

DOI_REGEX = r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+"


class ArxivLibGateway(ArxivGateway):
    def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> Iterator[ResearchPaper]:
        """
        Searches arXiv using the `arxiv` python library.
        """

        criterion_map = {
            "relevance": arxiv.SortCriterion.Relevance,
            "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
            "submittedDate": arxiv.SortCriterion.SubmittedDate,
        }

        order_map = {
            "ascending": arxiv.SortOrder.Ascending,
            "descending": arxiv.SortOrder.Descending,
        }

        criterion = criterion_map.get(sort_by, arxiv.SortCriterion.Relevance)
        order = order_map.get(sort_order, arxiv.SortOrder.Descending)

        # Construct the arXiv search object
        search = arxiv.Search(
            query=query, max_results=max_results, sort_by=criterion, sort_order=order
        )

        # Use the arxiv Client to execute the search
        client = arxiv.Client()

        results = client.results(search)

        for result in results:
            # Extract DOI with fallback
            doi = result.doi
            if not doi:
                # Secondary Target: Regex search on comment or journal_ref
                text_to_search = f"{result.comment or ''} {result.journal_ref or ''}"
                match = re.search(DOI_REGEX, text_to_search)
                if match:
                    doi = match.group(0)

            if doi:
                doi = doi.strip()

            # Map external library object to our internal Domain Model
            yield ResearchPaper(
                arxiv_id=result.get_short_id(),
                title=result.title,
                abstract=result.summary,
                authors=[a.name for a in result.authors],
                year=str(result.published.year) if result.published else None,
                doi=doi,
                url=result.pdf_url,
                publication=result.journal_ref,
            )
