import arxiv
from typing import Iterator
from paper2zotero.core.interfaces import ArxivGateway
from paper2zotero.core.models import ResearchPaper

class ArxivLibGateway(ArxivGateway):
    def search(self, query: str, limit: int = 100) -> Iterator[ResearchPaper]:
        """
        Searches arXiv using the `arxiv` python library.
        """
        # Construct the arXiv search object
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance
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