import concurrent.futures
from typing import List, Optional

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.utils.normalization import is_valid_doi, normalize_doi


class MetadataAggregatorService:
    def __init__(self, providers: List[MetadataProvider]):
        self.providers = providers
        # Optional direct access for importer clients
        self.semantic_scholar: Optional[MetadataProvider] = None
        self.crossref: Optional[MetadataProvider] = None
        self.unpaywall: Optional[MetadataProvider] = None
        self.openalex: Optional[MetadataProvider] = None
        self.pubmed: Optional[MetadataProvider] = None
        self.zbmath: Optional[MetadataProvider] = None
        self.eric: Optional[MetadataProvider] = None
        self.hal: Optional[MetadataProvider] = None
        self.inspire_hep: Optional[MetadataProvider] = None
        self.dblp: Optional[MetadataProvider] = None

    def get_enriched_metadata(
        self, identifier: str, require_doi_match: bool = False
    ) -> Optional[ResearchPaper]:
        """
        Queries all providers for metadata and merges the results into a single
        high-quality ResearchPaper object.

        With `require_doi_match` and a DOI identifier, only candidates that
        carry that same DOI are merged. Some providers (e.g. DBLP) run a
        free-text "best match" search on whatever they're given, and a
        wrong match with no DOI would otherwise contribute its venue or
        authors. Used where the result is written into existing items
        (`item hydrate`, Issue #344).
        """
        results: List[ResearchPaper] = []

        # Fetch from all providers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            future_to_provider = {
                executor.submit(provider.get_paper_metadata, identifier): provider
                for provider in self.providers
            }

            for future in concurrent.futures.as_completed(future_to_provider):
                try:
                    data = future.result()
                    if data:
                        results.append(data)
                except Exception as exc:
                    print(f"Provider generated an exception: {exc}")

        results = self._drop_mismatched_dois(identifier, results, require_doi_match)
        if not results:
            return None

        return self._merge_metadata(results)

    @staticmethod
    def _drop_mismatched_dois(
        identifier: str, candidates: List[ResearchPaper], require_doi_match: bool = False
    ) -> List[ResearchPaper]:
        """When the lookup is by DOI, a candidate carrying a different DOI
        describes another paper (e.g. a provider that misread the DOI) and
        must not be merged in, since the merge prefers the longest title and
        abstract (Issue #340). Candidates without a DOI are kept unless
        `require_doi_match`."""
        queried = normalize_doi(identifier)
        if not is_valid_doi(queried):
            return candidates

        def matches(c: ResearchPaper) -> bool:
            if not c.doi:
                return not require_doi_match
            return bool(normalize_doi(c.doi).lower() == queried.lower())

        return [c for c in candidates if matches(c)]

    def _merge_metadata(self, candidates: List[ResearchPaper]) -> ResearchPaper:
        """
        Merges a list of ResearchPaper objects using heuristics to select the best data.
        """
        base = ResearchPaper(title="", abstract="")

        # 1. Initialize sets for merging collections
        all_authors: List[str] = []
        all_references = set()

        best_title = ""
        best_abstract = ""
        best_year = None
        best_doi = None
        best_arxiv = None
        best_venue = ""
        best_url = None
        best_pdf_url = None
        best_extra = None

        for p in candidates:
            # Title Selection Strategy:
            # 1. Prefer mixed-case over all-caps
            # 2. Prefer longer titles (usually more complete)
            if not p.title:
                continue

            if not best_title:
                best_title = p.title
            else:
                current_is_upper = best_title.isupper()
                candidate_is_upper = p.title.isupper()

                if current_is_upper and not candidate_is_upper:
                    best_title = p.title
                elif not current_is_upper and candidate_is_upper:
                    pass  # Keep mixed case
                elif len(p.title) > len(best_title):
                    best_title = p.title

            # Abstract: Longest wins
            if p.abstract and len(p.abstract) > len(best_abstract):
                best_abstract = p.abstract

            # Year: Prefer any value over None
            if p.year and not best_year:
                best_year = p.year

            # Venue
            if p.publication and not best_venue:
                best_venue = p.publication

            # IDs
            if p.doi:
                best_doi = p.doi
            if p.arxiv_id:
                best_arxiv = p.arxiv_id
            if p.url:
                best_url = p.url
            if p.pdf_url:
                best_pdf_url = p.pdf_url

            # Extra
            if p.extra:
                if not best_extra:
                    best_extra = p.extra
                else:
                    current_lines = set(best_extra.split("\n"))
                    new_lines = [line for line in p.extra.split("\n") if line not in current_lines]
                    if new_lines:
                        best_extra += "\n" + "\n".join(new_lines)

            # Authors: Pick the list with the most authors (avoids et al.)
            if len(p.authors) > len(all_authors):
                all_authors = p.authors

            # References: Union
            all_references.update(p.references)

        base.title = self._clean_title(best_title)
        base.abstract = best_abstract
        base.authors = all_authors
        base.year = best_year
        base.publication = best_venue
        base.doi = best_doi
        base.arxiv_id = best_arxiv
        base.url = best_url
        base.pdf_url = best_pdf_url
        base.extra = best_extra
        base.references = list(all_references)
        base.citation_count = len(all_references)

        return base

    def _clean_title(self, title: str) -> str:
        if not title:
            return ""
        return title.strip()
