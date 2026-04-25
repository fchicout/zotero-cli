from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .zotero_item import ZoteroItem


class ScreeningStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    UNKNOWN = "unknown"


@dataclass
class ResearchPaper:
    title: str
    abstract: str
    key: Optional[str] = None
    arxiv_id: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    publication: Optional[str] = None
    year: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    references: List[str] = field(default_factory=list)
    citation_count: Optional[int] = None
    extra: Optional[str] = None
    sdb_metadata: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ZoteroQuery:
    """
    Encapsulates Zotero API search parameters.
    See: https://www.zotero.org/support/dev/web_api/v3/basics#search_syntax
    """

    q: Optional[str] = None
    qmode: Optional[str] = "titleCreatorYear"  # 'titleCreatorYear' or 'everything'
    item_type: Optional[str] = None
    tag: Optional[str] = None
    since: Optional[int] = None
    sort: Optional[str] = "date"
    direction: Optional[str] = "desc"  # 'asc' or 'desc'

    def to_params(self) -> dict:
        params: Dict[str, Any] = {}
        if self.q:
            params["q"] = self.q
        if self.qmode:
            params["qmode"] = self.qmode
        if self.item_type:
            params["itemType"] = self.item_type
        if self.tag:
            params["tag"] = self.tag
        if self.since:
            params["since"] = self.since
        if self.sort:
            params["sort"] = self.sort
        if self.direction:
            params["direction"] = self.direction
        return params


@dataclass
class Job:
    item_key: str
    task_type: str
    payload: Dict[str, Any]
    id: Optional[int] = None
    status: str = "PENDING"
    attempts: int = 0
    next_retry_at: Optional[str] = None
    last_error: Optional[str] = None


@dataclass
class VectorChunk:
    item_key: str
    chunk_index: int
    text: str
    embedding: List[float]
    citation_key: Optional[str] = None
    qa_score: Optional[float] = None
    phase_folder: Optional[str] = None
    id: Optional[int] = None


@dataclass
class SearchResult:
    item_key: str
    text: str
    score: float
    metadata: Dict[str, Any]
    item: Optional[ZoteroItem] = None


@dataclass
class VerifiedSearchResult(SearchResult):
    is_verified: bool = False
    verification_errors: List[str] = field(default_factory=list)
    screening_status: ScreeningStatus = ScreeningStatus.UNKNOWN
    citation_key: Optional[str] = None
