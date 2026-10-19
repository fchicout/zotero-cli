import re
from typing import Iterator

import arxiv

from zotero_cli.core.exceptions import Unavailable
from zotero_cli.core.interfaces import ArxivGateway
from zotero_cli.core.models import ResearchPaper

DOI_REGEX = r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+"

# arXiv asks API clients for at most one request every three seconds. The library waits
# `delay_seconds` between requests and retries a failed one `num_retries` times, so a
# service that is rejecting us (HTTP 429) costs a few seconds, not minutes of hammering
# it (it used to be ten retries five seconds apart).
ARXIV_DELAY_SECONDS = 3.0
ARXIV_RETRIES = 2


def _client() -> arxiv.Client:
    return arxiv.Client(num_retries=ARXIV_RETRIES, delay_seconds=ARXIV_DELAY_SECONDS)


def _unavailable(error: arxiv.HTTPError) -> Unavailable:
    """A failed arXiv request as the CLI's own error (exit 5) with a message that says what
    to do, instead of the library's traceback."""
    if error.status == 429:
        return Unavailable(
            "arXiv is rate limiting requests from this address (HTTP 429). Wait a while "
            "(often an hour) and try again; the API allows one request every 3 seconds."
        )
    return Unavailable(f"arXiv could not be reached (HTTP {error.status}); try again later.")


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

        results = _client().results(search)

        try:
            yield from self._map_results(results)
        except arxiv.HTTPError as error:
            raise _unavailable(error) from error

    @staticmethod
    def _map_results(results: Iterator[arxiv.Result]) -> Iterator[ResearchPaper]:
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
                pdf_url=result.pdf_url,
                publication=result.journal_ref,
            )

    def count(self, query: str) -> int:
        """
        Returns the total result count for a query, reading it straight off
        the Atom feed's <opensearch:totalResults> from a single-item page
        request rather than fetching/discarding up to max_results full
        results just to count them (Issue #181).

        `arxiv.Client.results()`/`._results()` already fetches this same
        total as part of the first page's feed metadata
        (`feed.header.total_results`) - it's just not surfaced through the
        public API, so this reaches one layer down to `_format_url`/
        `_parse_feed` (both are the library's own internal helpers, not
        third-party-private state we're guessing at).
        """
        search = arxiv.Search(query=query, max_results=1)
        client = _client()
        url = client._format_url(search, 0, 1)
        try:
            feed = client._parse_feed(url, first_page=True)
        except arxiv.HTTPError as error:
            raise _unavailable(error) from error
        return int(feed.header.total_results)
