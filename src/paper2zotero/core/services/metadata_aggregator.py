from typing import List, Optional
import concurrent.futures
import re
import unicodedata
from paper2zotero.core.interfaces import MetadataProvider
from paper2zotero.core.models import ResearchPaper

class MetadataAggregatorService:
    def __init__(self, providers: List[MetadataProvider]):
        self.providers = providers

    def get_enriched_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Queries all providers for metadata and merges the results into a single
        high-quality ResearchPaper object.
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

        if not results:
            return None

        return self._merge_metadata(results)

    def _merge_metadata(self, candidates: List[ResearchPaper]) -> ResearchPaper:
        """
        Merges a list of ResearchPaper objects using heuristics to select the best data.
        """
        base = ResearchPaper(title="", abstract="")
        
        # 1. Initialize sets for merging collections
        all_authors = []
        all_references = set()
        
        best_title = ""
        best_abstract = ""
        best_year = None
        best_doi = None
        best_arxiv = None
        best_venue = ""
        best_url = None
        best_pdf_url = None

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
                    pass # Keep mixed case
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
            if p.doi: best_doi = p.doi
            if p.arxiv_id: best_arxiv = p.arxiv_id
            if p.url: best_url = p.url
            if p.pdf_url: best_pdf_url = p.pdf_url

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
        base.references = list(all_references)
        base.citation_count = len(all_references)

        return base

    def _clean_title(self, title: str) -> str:
        if not title: return ""
        return title.strip()
