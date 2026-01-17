import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ZoteroItem:
    key: str
    version: int
    item_type: str
    collections: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    title: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    date: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    has_pdf: bool = False  # Will be set by auditor or via child items processing later
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw_zotero_item(cls, raw_item: Dict[str, Any]) -> "ZoteroItem":
        data = raw_item.get("data", {})

        # Extract DOI
        doi = data.get("DOI")

        # Extract arXiv ID
        arxiv_id = None
        extra = data.get("extra", "")
        arxiv_match = re.search(r"arXiv:\s*([\d.]+v?\d*)", extra, re.IGNORECASE)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
        elif data.get("url") and "arxiv.org" in data["url"]:
            url_match = re.search(r"(?:arxiv\.org/abs/|arxiv\.org/pdf/)([\d.]+)", data["url"])
            if url_match:
                arxiv_id = url_match.group(1)

        tags = [t.get("tag") for t in data.get("tags", []) if "tag" in t]

        # Extract Authors
        authors = []
        creators = data.get("creators", [])
        for creator in creators:
            if creator.get("creatorType") == "author":
                if "firstName" in creator and "lastName" in creator:
                    authors.append(f"{creator['firstName']} {creator['lastName']}")
                elif "name" in creator:
                    authors.append(creator["name"])

        return cls(
            key=raw_item["key"],
            version=data.get("version", 0),
            item_type=data.get("itemType", "unknown"),
            title=data.get("title"),
            abstract=data.get("abstractNote"),
            doi=doi,
            arxiv_id=arxiv_id,
            url=data.get("url"),
            date=data.get("date"),
            authors=authors,
            collections=data.get("collections", []),
            tags=tags,
            has_pdf=False,  # Default, actual check done by service
            raw_data=raw_item,
        )

    def has_identifier(self) -> bool:
        return self.doi is not None or self.arxiv_id is not None
