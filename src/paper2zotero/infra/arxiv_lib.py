import arxiv
from typing import Iterator
from paper2zotero.core.interfaces import ArxivGateway
from paper2zotero.core.models import ArxivPaper

class ArxivLibGateway(ArxivGateway):
    def search(self, query: str, limit: int = 100) -> Iterator[ArxivPaper]:
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
        # (Client handles pagination automatically behind the scenes)
        client = arxiv.Client()
        
        results = client.results(search)

        for result in results:
            # Map external library object to our internal Domain Model
            yield ArxivPaper(
                arxiv_id=result.get_short_id(), # Extract short ID like "2301.00001v1"
                title=result.title,
                abstract=result.summary
            )
