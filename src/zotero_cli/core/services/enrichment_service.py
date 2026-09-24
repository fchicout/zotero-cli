"""
`item hydrate`: fill in missing metadata from external sources (Issue #344).

For each item the service finds an identifier (DOI, then arXiv ID, then a
PMID in `extra`; optionally a high-confidence title match), looks the work
up through the metadata aggregator, and proposes values for fields that are
empty. Existing values are only replaced with `overwrite`, and never the
title unless it's asked for explicitly. Nothing is written unless `execute`
is set; the same report describes both the preview and the applied result.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from zotero_cli.core.interfaces import (
    ArxivGateway,
    CollectionRepository,
    ItemRepository,
    SearchableMetadataProvider,
)
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.utils.normalization import is_valid_doi, normalize_doi, normalize_title
from zotero_cli.core.zotero_item import ZoteroItem

# Friendly field names accepted by --fields, in report order.
HYDRATABLE_FIELDS = ("doi", "abstract", "date", "venue", "url", "creators", "title")
# Written by default. `title` is only ever written when named in --fields.
DEFAULT_FIELDS = ("doi", "abstract", "date", "venue", "url", "creators")

# Zotero stores a work's venue under a different field per item type; the
# first one the item's type has is used.
_VENUE_FIELDS = ("publicationTitle", "proceedingsTitle", "bookTitle", "conferenceName")
_FIELD_TO_ZOTERO = {
    "doi": "DOI",
    "abstract": "abstractNote",
    "date": "date",
    "url": "url",
    "creators": "creators",
    "title": "title",
}
# Items that are never hydrated: children and standalone non-works.
_SKIPPED_TYPES = {"attachment", "note", "annotation"}
_PMID_RE = re.compile(r"^\s*PMID:\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE)
_YEAR_RE = re.compile(r"\b(\d{4})\b")


@dataclass
class HydrationResult:
    key: str
    title: str
    status: str  # updated | proposed | no-change | no-identifier | not-found | failed
    identifier: Optional[str] = None
    source: Optional[str] = None
    changes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "status": self.status,
            "identifier": self.identifier,
            "source": self.source,
            "changes": self.changes,
            "message": self.message,
        }


def parse_fields(spec: Optional[str]) -> Tuple[str, ...]:
    """Turns a --fields value into friendly field names (the default set
    if empty). Raises ValueError on an unknown name."""
    if not spec:
        return DEFAULT_FIELDS
    fields = tuple(f.strip().lower() for f in spec.split(",") if f.strip())
    unknown = [f for f in fields if f not in HYDRATABLE_FIELDS]
    if unknown:
        raise ValueError(
            f"Unknown field(s): {', '.join(unknown)}. Choose from: {', '.join(HYDRATABLE_FIELDS)}"
        )
    return fields


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _year(value: Optional[str]) -> Optional[str]:
    match = _YEAR_RE.search(value or "")
    return match.group(1) if match else None


def _creators_from_names(names: Sequence[str]) -> List[Dict[str, str]]:
    creators = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        if " " in name:
            first, last = name.rsplit(" ", 1)
            creators.append({"creatorType": "author", "firstName": first, "lastName": last})
        else:
            creators.append({"creatorType": "author", "name": name})
    return creators


def _last_name(name: str) -> str:
    name = name.strip()
    if "," in name:
        return name.split(",", 1)[0].strip().lower()
    return name.rsplit(" ", 1)[-1].lower() if name else ""


class EnrichmentService:
    def __init__(
        self,
        item_repo: ItemRepository,
        collection_repo: CollectionRepository,
        arxiv_gateway: ArxivGateway,
        metadata_aggregator: Optional[MetadataAggregatorService] = None,
        title_searcher: Optional[SearchableMetadataProvider] = None,
    ):
        self.item_repo = item_repo
        self.collection_repo = collection_repo
        self.arxiv_gateway = arxiv_gateway
        self.metadata_aggregator = metadata_aggregator
        self.title_searcher = title_searcher

    # --- Scopes ---------------------------------------------------------

    def hydrate_item(self, item_key: str, **options: Any) -> Optional[HydrationResult]:
        item = self.item_repo.get_item(item_key)
        if not item:
            return None
        return self.hydrate(item, **options)

    def hydrate_collection(self, collection_id: str, **options: Any) -> List[HydrationResult]:
        items = self.collection_repo.get_items_in_collection(collection_id, top_only=True)
        return self.hydrate_many(items, **options)

    def hydrate_all(self, **options: Any) -> List[HydrationResult]:
        # A client-side scan of the whole library: Zotero's search can't
        # reliably select "items with a DOI or arXiv ID" (Issue #205).
        return self.hydrate_many(self.item_repo.get_all_items(), **options)

    def hydrate_many(self, items: Iterable[ZoteroItem], **options: Any) -> List[HydrationResult]:
        return [self.hydrate(item, **options) for item in self._top_level_works(items)]

    @staticmethod
    def _top_level_works(items: Iterable[ZoteroItem]) -> Iterator[ZoteroItem]:
        for item in items:
            if item.item_type not in _SKIPPED_TYPES and not item.parent_item:
                yield item

    # --- One item -------------------------------------------------------

    def hydrate(
        self,
        item: ZoteroItem,
        fields: Sequence[str] = DEFAULT_FIELDS,
        overwrite: bool = False,
        by_title: bool = False,
        execute: bool = False,
    ) -> HydrationResult:
        result = HydrationResult(key=item.key, title=item.title or "Untitled", status="no-change")
        try:
            identifier, paper, source = self._lookup(item, by_title)
        except Exception as e:  # one provider failure shouldn't stop a batch
            result.status, result.message = "failed", f"Lookup failed: {e}"
            return result
        result.identifier, result.source = identifier, source
        if identifier is None:
            result.status = "no-identifier"
            result.message = "No DOI, arXiv ID or PMID" + ("" if by_title else " (try --by-title)")
            return result
        if paper is None:
            result.status = "not-found"
            return result

        result.changes = self._proposed_changes(item, paper, fields, overwrite)
        if not result.changes:
            return result
        if not execute:
            result.status = "proposed"
            return result

        payload = {name: change["new"] for name, change in result.changes.items()}
        try:
            ok = self.item_repo.update_item(item.key, item.version, payload)
        except Exception as e:
            result.status, result.message = "failed", f"Update failed: {e}"
            return result
        result.status = "updated" if ok else "failed"
        if not ok:
            result.message = "Zotero rejected the update"
        return result

    def _lookup(
        self, item: ZoteroItem, by_title: bool
    ) -> Tuple[Optional[str], Optional[ResearchPaper], Optional[str]]:
        """Returns (identifier used, merged metadata, source description)."""
        doi = normalize_doi(item.doi or "")
        if is_valid_doi(doi):
            return f"doi:{doi}", self._by_doi(doi), "metadata providers"

        if item.arxiv_id:
            return self._lookup_arxiv(item.arxiv_id)

        pmid_match = _PMID_RE.search(item.extra or "")
        if pmid_match and self.metadata_aggregator:
            pmid = pmid_match.group(1)
            return f"pmid:{pmid}", self.metadata_aggregator.get_enriched_metadata(pmid), "PubMed"

        if by_title and item.title:
            match = self._confident_title_match(item)
            if match is None:
                return "title", None, None
            match_doi = normalize_doi(match.doi or "")
            if is_valid_doi(match_doi):
                return "title", self._by_doi(match_doi) or match, "title match + metadata providers"
            return "title", match, "title match"

        return None, None, None

    def _lookup_arxiv(
        self, arxiv_id: str
    ) -> Tuple[Optional[str], Optional[ResearchPaper], Optional[str]]:
        # A preprint: arXiv knows the DOI and journal of the published
        # version once there is one; the providers then fill in the rest.
        identifier = f"arxiv:{arxiv_id}"
        arxiv_paper = next(iter(self.arxiv_gateway.search(f"id:{arxiv_id}", max_results=1)), None)
        if arxiv_paper is None:
            return identifier, None, None
        published_doi = normalize_doi(arxiv_paper.doi or "")
        if not is_valid_doi(published_doi):
            return identifier, arxiv_paper, "arXiv"
        merged = self._by_doi(published_doi)
        if merged is None:
            return identifier, arxiv_paper, "arXiv"
        merged.doi = merged.doi or published_doi
        merged.publication = merged.publication or arxiv_paper.publication
        return identifier, merged, "arXiv + metadata providers"

    def _by_doi(self, doi: str) -> Optional[ResearchPaper]:
        if self.metadata_aggregator is None:
            return None
        # Only records carrying this exact DOI are merged: the result is
        # written into an existing item, so a provider's misread or
        # best-guess match must not leak in (Issues #340, #344).
        return self.metadata_aggregator.get_enriched_metadata(doi, require_doi_match=True)

    def _confident_title_match(self, item: ZoteroItem) -> Optional[ResearchPaper]:
        """Only an exact normalized-title match counts, and it must also
        agree on the year and the first author's last name when the item
        has them. Anything less is reported as "not found", not guessed."""
        if self.title_searcher is None or not item.title:
            return None
        wanted_title = normalize_title(item.title)
        wanted_year = _year(item.date)
        wanted_author = _last_name(item.authors[0]) if item.authors else None
        for candidate in self.title_searcher.search(item.title, max_results=5):
            if normalize_title(candidate.title) != wanted_title:
                continue
            if wanted_year and _year(candidate.year) not in (None, wanted_year):
                continue
            if wanted_author and candidate.authors:
                if _last_name(candidate.authors[0]) != wanted_author:
                    continue
            return candidate
        return None

    # --- Field changes --------------------------------------------------

    def _proposed_changes(
        self, item: ZoteroItem, paper: ResearchPaper, fields: Sequence[str], overwrite: bool
    ) -> Dict[str, Dict[str, Any]]:
        data = item.raw_data.get("data", {}) if isinstance(item.raw_data, dict) else {}
        venue_field = next((f for f in _VENUE_FIELDS if f in data), None)
        candidates: Dict[str, Any] = {
            "doi": normalize_doi(paper.doi) if paper.doi else None,
            "abstract": paper.abstract or None,
            "date": paper.year or None,
            "venue": paper.publication or None,
            # A DOI resolver link is stable and publisher-neutral; a
            # provider's own page (PubMed, arXiv, ...) is the fallback.
            "url": f"https://doi.org/{normalize_doi(paper.doi)}" if paper.doi else paper.url or None,
            "creators": _creators_from_names(paper.authors) or None,
            "title": paper.title or None,
        }
        changes: Dict[str, Dict[str, Any]] = {}
        for name in fields:
            zotero_field = venue_field if name == "venue" else _FIELD_TO_ZOTERO[name]
            new = candidates[name]
            # Only fields the item's type actually has: the Web API returns
            # every valid field for the type, empty or not, and rejects
            # writes to any other.
            if zotero_field is None or zotero_field not in data or new is None:
                continue
            old = data.get(zotero_field)
            if self._keep_existing(name, old, new, overwrite):
                continue
            changes[zotero_field] = {"old": old, "new": new}
        return changes

    @staticmethod
    def _keep_existing(name: str, old: Any, new: Any, overwrite: bool) -> bool:
        if _is_empty(old):
            return False
        if not overwrite or old == new:
            return True
        if name == "doi":
            return bool(normalize_doi(str(old)) == new)
        if name == "date":
            # Providers only give a year; never replace a full date that
            # already has that year with the bare year.
            return bool(_year(str(old)) == new)
        return False
