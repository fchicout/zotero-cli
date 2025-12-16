from dataclasses import dataclass, field
from typing import List, Optional

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