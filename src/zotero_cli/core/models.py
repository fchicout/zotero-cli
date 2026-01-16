from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ResearchPaper:
    title: str
    abstract: str
    arxiv_id: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    publication: Optional[str] = None
    year: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    references: List[str] = field(default_factory=list)
    citation_count: Optional[int] = None

@dataclass
class ZoteroQuery:
    """
    Encapsulates Zotero API search parameters.
    See: https://www.zotero.org/support/dev/web_api/v3/basics#search_syntax
    """
    q: Optional[str] = None
    qmode: Optional[str] = "titleCreatorYear" # 'titleCreatorYear' or 'everything'
    item_type: Optional[str] = None
    tag: Optional[str] = None
    since: Optional[int] = None
    sort: Optional[str] = "date"
    direction: Optional[str] = "desc" # 'asc' or 'desc'

    def to_params(self) -> dict:
        params: Dict[str, Any] = {}
        if self.q:
            params['q'] = self.q
        if self.qmode:
            params['qmode'] = self.qmode
        if self.item_type:
            params['itemType'] = self.item_type
        if self.tag:
            params['tag'] = self.tag
        if self.since:
            params['since'] = self.since
        if self.sort:
            params['sort'] = self.sort
        if self.direction:
            params['direction'] = self.direction
        return params
