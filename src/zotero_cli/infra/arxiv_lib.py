from typing import Iterator

import arxiv

from zotero_cli.core.interfaces import ArxivGateway
from zotero_cli.core.models import ResearchPaper


class ArxivLibGateway(ArxivGateway):
    def search(self, query: str, limit: int = 100, sort_by: str = "relevance", sort_order: str = "descending") -> Iterator[ResearchPaper]:
        """
        Searches arXiv using the `arxiv` python library.
        """

        criterion_map = {
            "relevance": arxiv.SortCriterion.Relevance,
            "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
            "submittedDate": arxiv.SortCriterion.SubmittedDate
        }

        order_map = {
            "ascending": arxiv.SortOrder.Ascending,
            "descending": arxiv.SortOrder.Descending
        }

        criterion = criterion_map.get(sort_by, arxiv.SortCriterion.Relevance)
        order = order_map.get(sort_order, arxiv.SortOrder.Descending)

        # Construct the arXiv search object
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=criterion,
            sort_order=order
        )

        # Use the arxiv Client to execute the search
        client = arxiv.Client()

        results = client.results(search)

        for result in results:
            # Map external library object to our internal Domain Model
            yield ResearchPaper(
                arxiv_id=result.get_short_id(),
                title=result.title,
                abstract=result.summary,
                authors=[a.name for a in result.authors],
                year=str(result.published.year) if result.published else None,
                doi=result.doi,
                url=result.pdf_url,
                publication=result.journal_ref
            )
