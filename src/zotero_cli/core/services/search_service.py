"""One search for every front end: keyword, filters, sorting, paging and PDF text.

`search` (the CLI) and the MCP server's `search_items` both run through here, so a
filter means the same thing in both (Issues #557, #560, #562).
"""

from dataclasses import dataclass
from itertools import islice
from typing import Iterable, Iterator, Optional, Sequence, Tuple

from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.interfaces import ItemSearch
from zotero_cli.core.models import ZoteroQuery
from zotero_cli.core.utils import search_filters
from zotero_cli.core.utils.search_filters import YearRange
from zotero_cli.core.zotero_item import ZoteroItem

Hit = Tuple[ZoteroItem, Optional[float]]


@dataclass(frozen=True)
class SearchRequest:
    # The words to look for: title, creator and year, or with `fulltext` the PDFs' text.
    text: Optional[str] = None
    tags: Sequence[str] = ()
    item_type: Optional[str] = None
    collection_key: Optional[str] = None  # an already resolved key
    years: Optional[YearRange] = None
    added_since: Optional[str] = None
    added_until: Optional[str] = None
    sort: Optional[str] = None
    direction: Optional[str] = None
    fulltext: bool = False
    start: int = 0
    limit: int = 50  # 0 or less: no limit

    def query(self) -> ZoteroQuery:
        """The server-side part: the keyword (not for full text), tags, type, collection and
        the sort. Year and date added are applied here as results arrive."""
        query = ZoteroQuery(
            q=None if self.fulltext else self.text,
            qmode="titleCreatorYear",
            item_type=self.item_type,
            tag=list(self.tags) or None,
            collection=self.collection_key,
        )
        if self.sort:
            query.sort = self.sort
        if self.direction:
            query.direction = self.direction
        return query


class SearchService:
    def __init__(self, gateway: ItemSearch):
        self.gateway = gateway

    @staticmethod
    def window(hits: Iterable, start: int, limit: int) -> Iterator:
        """Skip `start`, then stop after `limit`. Reading stops with it: results arrive a
        page at a time and every page used to be fetched first (Issue #438)."""
        stop = start + limit if limit and limit > 0 else None
        return islice(hits, start, stop)

    def search(self, request: SearchRequest) -> Iterator[Hit]:
        """(item, score) pairs: score is the relevance for full text and None otherwise.
        The gateway is asked at once, so its errors surface here, not on first use."""
        if request.start < 0:
            raise UsageError("--start can't be negative.")
        stream: Iterator[Hit]
        if request.fulltext:
            if not request.text:
                raise UsageError("Full-text search needs words to look for.")
            stream = iter(self.gateway.search_fulltext(request.text, request.query()))
        else:
            stream = ((item, None) for item in self.gateway.search_items(request.query()))
        if (
            request.years is not None
            or request.added_since is not None
            or request.added_until is not None
        ):
            stream = (
                hit
                for hit in stream
                if search_filters.matches(
                    hit[0], request.years, request.added_since, request.added_until
                )
            )
        return self.window(stream, request.start, request.limit)
