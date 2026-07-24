import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem


@dataclass
class DuplicateOccurrence:
    """One item's appearance within a DuplicateGroup."""

    key: str
    collection_id: str
    title: Optional[str] = None


@dataclass
class DuplicateGroup:
    """
    A set of items detected as duplicates of one another.

    `match_type` is one of "doi" / "isbn" / "arxiv" / "title" (exact tier) or
    "fuzzy" / "preprint-published-pair" (fallback tier). `identifier` is the
    normalized value that caused the match (a DOI, ISBN, ArXiv ID, or title).
    """

    match_type: str
    identifier: str
    occurrences: List[DuplicateOccurrence] = field(default_factory=list)


class DuplicateFinder:
    """
    Finder service to detect duplicate research items across different collections.
    Supports matching items by DOI, ISBN, ArXiv ID, or normalized title (exact tier),
    with a fuzzy year/author/title fallback tier for `compare_collections` that
    reaches (and, for preprint/published pairs, exceeds) Zotero Desktop's own
    duplicate-detection algorithm (https://www.zotero.org/support/duplicate_detection).

    Directly importable/callable by external consumers (e.g. Corbenic-SLR): no
    stdout side effects and no bare-dict return shapes. Non-fatal issues found
    while scanning (e.g. a named collection that doesn't exist) are collected
    in `self.warnings` after each call instead of being printed, so callers can
    decide whether/how to surface them.
    """

    # Same-item-type is required for a real merge in Zotero Desktop, but a preprint
    # and its later published version are a distinct, common SLR case worth surfacing
    # rather than silently dropping just because item types differ.
    PREPRINT_TYPES = {"preprint"}
    PUBLISHED_TYPES = {"journalArticle", "conferencePaper"}

    # SequenceMatcher ratio threshold for the fuzzy title fallback tier. Different
    # database exports of the same paper commonly differ in subtitle truncation,
    # punctuation, or capitalization beyond what `_normalize_title` already strips.
    FUZZY_TITLE_THRESHOLD = 0.85

    _YEAR_RE = re.compile(r"(19|20)\d{2}")

    def __init__(self, gateway: ZoteroGateway):
        """
        Initializes the DuplicateFinder with a Zotero gateway.
        """
        self.gateway = gateway
        self.warnings: List[str] = []

    def find_duplicates(self, collection_ids: List[str]) -> List[DuplicateGroup]:
        """
        Analyzes the specified collections to find duplicate Zotero items
        (exact tier only: DOI / ISBN / ArXiv / normalized title).
        """
        self.warnings = []
        items_with_scope = self._collect_from_collections(collection_ids)

        all_items_by_identifier: Dict[Tuple[str, str], List[Tuple[ZoteroItem, str]]] = defaultdict(
            list
        )
        for item, scope in items_with_scope:
            identifier = self._identifier_for(item)
            if identifier:
                all_items_by_identifier[identifier].append((item, scope))

        return [
            self._build_group(id_type, identifier_value, occurrences)
            for (id_type, identifier_value), occurrences in all_items_by_identifier.items()
            if len(occurrences) > 1
        ]

    def compare_collections(
        self, collection_ids: Optional[List[str]] = None
    ) -> List[DuplicateGroup]:
        """
        Like `find_duplicates`, but preserves which collection each duplicate
        occurrence came from, for read-only cross-collection duplicate reports
        (e.g. `report duplicates`) that need to show provenance rather than
        just a pooled list of keys.

        `collection_ids=None` scans the whole library instead of specific
        collections, matching Zotero Desktop's own default detection scope.

        In addition to exact DOI/ISBN/ArXiv/title matching, items that don't
        exactly match anything else are run through a fuzzy fallback tier
        (fuzzy title similarity + publication year within 1 year + at least one
        shared author last-name/first-initial), the same corroborating-signal
        approach Desktop uses for items whose primary fields don't cleanly
        resolve on their own.
        """
        self.warnings = []
        items_with_scope = self._collect_items(collection_ids)

        all_items_by_identifier: Dict[Tuple[str, str], List[Tuple[ZoteroItem, str]]] = defaultdict(
            list
        )
        for item, scope in items_with_scope:
            identifier = self._identifier_for(item)
            if identifier:
                all_items_by_identifier[identifier].append((item, scope))

        duplicates = []
        singletons: List[Tuple[ZoteroItem, str]] = []
        for (id_type, identifier_value), occurrences in all_items_by_identifier.items():
            if len(occurrences) > 1:
                duplicates.append(self._build_group(id_type, identifier_value, occurrences))
            else:
                singletons.extend(occurrences)

        duplicates.extend(self._fuzzy_fallback_groups(singletons))
        return duplicates

    def _build_group(
        self, match_type: str, identifier: str, occurrences: List[Tuple[ZoteroItem, str]]
    ) -> DuplicateGroup:
        return DuplicateGroup(
            match_type=match_type,
            identifier=identifier,
            occurrences=[
                DuplicateOccurrence(key=item.key, collection_id=scope, title=item.title)
                for item, scope in occurrences
            ],
        )

    def _collect_items(
        self, collection_ids: Optional[List[str]]
    ) -> List[Tuple[ZoteroItem, str]]:
        if collection_ids is None:
            return [
                (item, item.collections[0] if item.collections else "UNFILED")
                for item in self.gateway.get_all_items()
            ]
        return self._collect_from_collections(collection_ids)

    def _collect_from_collections(
        self, collection_ids: List[str]
    ) -> List[Tuple[ZoteroItem, str]]:
        items_with_scope: List[Tuple[ZoteroItem, str]] = []
        for col_id in collection_ids:
            for item in self._fetch_collection_items(col_id):
                items_with_scope.append((item, col_id))
        return items_with_scope

    def _fetch_collection_items(self, col_id: str) -> List[ZoteroItem]:
        # col_id is already expected to be a Zotero Key/ID
        items = list(self.gateway.get_items_in_collection(col_id))
        if not items and not self.gateway.get_collection(col_id):
            self.warnings.append(f"Collection '{col_id}' not found or empty. Skipping.")
            return []
        return items

    def _identifier_for(self, item: ZoteroItem) -> Optional[Tuple[str, str]]:
        normalized_doi = self._normalize_doi(item.doi) if item.doi else None
        normalized_isbn = self._normalize_isbn(item.isbn) if item.isbn else None
        normalized_arxiv = item.arxiv_id.strip().lower() if item.arxiv_id else None
        normalized_title = self._normalize_title(item.title) if item.title else None

        if normalized_doi:
            return ("doi", normalized_doi)
        if normalized_isbn:
            return ("isbn", normalized_isbn)
        if normalized_arxiv:
            return ("arxiv", normalized_arxiv)
        if normalized_title:
            return ("title", normalized_title)
        return None

    def _fuzzy_fallback_groups(
        self, singletons: List[Tuple[ZoteroItem, str]]
    ) -> List[DuplicateGroup]:
        """
        Pairwise fallback over items that didn't exactly match anything else:
        fuzzy title similarity + year-within-1 + shared author signature, all
        three required together. Connected via union-find so a chain of 3+
        near-duplicates still groups as one entry.
        """
        n = len(singletons)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        # Precompute per-item comparable fields once.
        norm_titles: List[Optional[str]] = []
        years: List[Optional[int]] = []
        author_sigs: List[Set[str]] = []
        for item, _ in singletons:
            norm_titles.append(self._normalize_title(item.title) if item.title else None)
            years.append(self._extract_year(item.date))
            author_sigs.append(self._author_signatures(item))

        component_label: Dict[int, str] = {}

        for i in range(n):
            title_i, year_i, authors_i = norm_titles[i], years[i], author_sigs[i]
            if not title_i or year_i is None or not authors_i:
                continue
            for j in range(i + 1, n):
                title_j, year_j, authors_j = norm_titles[j], years[j], author_sigs[j]
                if not title_j or year_j is None or not authors_j:
                    continue
                if abs(year_i - year_j) > 1:
                    continue
                if not (authors_i & authors_j):
                    continue
                if self._title_similarity(title_i, title_j) < self.FUZZY_TITLE_THRESHOLD:
                    continue

                item_i, _ = singletons[i]
                item_j, _ = singletons[j]
                label = self._classify_type_pair(item_i.item_type, item_j.item_type)
                if label is None:
                    continue

                union(i, j)
                root = find(i)
                if component_label.get(root) != "preprint-published-pair":
                    component_label[root] = label

        groups_by_root: Dict[int, List[int]] = defaultdict(list)
        for idx in range(n):
            groups_by_root[find(idx)].append(idx)

        results = []
        for root, idxs in groups_by_root.items():
            if len(idxs) < 2:
                continue
            label = component_label.get(root, "fuzzy")
            representative_title = norm_titles[idxs[0]] or ""
            results.append(
                DuplicateGroup(
                    match_type=label,
                    identifier=representative_title,
                    occurrences=[
                        DuplicateOccurrence(
                            key=singletons[idx][0].key,
                            collection_id=singletons[idx][1],
                            title=singletons[idx][0].title,
                        )
                        for idx in idxs
                    ],
                )
            )
        return results

    def _classify_type_pair(self, type_a: str, type_b: str) -> Optional[str]:
        if type_a == type_b:
            return "fuzzy"
        types = {type_a, type_b}
        if (types & self.PREPRINT_TYPES) and (types & self.PUBLISHED_TYPES):
            return "preprint-published-pair"
        return None

    def _author_signatures(self, item: ZoteroItem) -> Set[str]:
        signatures: Set[str] = set()
        for creator in item.creators:
            if creator.get("creatorType") != "author":
                continue
            last = (creator.get("lastName") or "").strip().lower()
            first = (creator.get("firstName") or "").strip().lower()
            if last and first:
                signatures.add(f"{last} {first[0]}")
            elif last:
                signatures.add(last)
            elif creator.get("name"):
                signatures.add(creator["name"].strip().lower())
        return signatures

    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        if not date_str:
            return None
        match = self._YEAR_RE.search(date_str)
        return int(match.group(0)) if match else None

    def _title_similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _normalize_doi(self, doi: str) -> str:
        return doi.strip().lower()

    def _normalize_isbn(self, isbn: str) -> str:
        return re.sub(r"[\s-]", "", isbn).strip().lower()

    def _normalize_title(self, title: str) -> str:
        # Lowercase
        title = title.lower()

        # Decompose unicode characters and remove non-spacing marks (accents)
        normalized_title = unicodedata.normalize("NFD", title)
        title = "".join(c for c in normalized_title if unicodedata.category(c) != "Mn")

        # Remove punctuation
        title = re.sub(r"[^\w\s]", "", title)

        # Replace multiple spaces with single space and strip
        title = re.sub(r"\s+", " ", title).strip()

        return title
