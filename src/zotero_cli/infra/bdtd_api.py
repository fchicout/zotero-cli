import logging
import urllib.parse
from typing import Any, Dict, Iterator, Optional, cast

from bs4 import BeautifulSoup
from rapidfuzz.distance import Levenshtein

from zotero_cli.core.interfaces import MetadataProvider, SearchableMetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.utils.url_safety import safe_get_text, safe_head
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

DOI_ORG = "doi.org/"

# Fields requested from BDTD's VuFind API - shared between get_paper_metadata
# and search() so both map the same record shape.
_RECORD_FIELDS = [
    "id",
    "title",
    "authors",
    "urls",
    "summary",
    "publicationDates",
    "institutions",
    "formats",
    "languages",
    "subjects",
]

# BDTD's VuFind search endpoint's max results per page.
_MAX_PER_PAGE = 20

# VuFind's repeated-query-param syntax for requesting specific fields.
_FIELD_PARAM = "field[]"


class BDTDAPIClient(BaseAPIClient, MetadataProvider, SearchableMetadataProvider):
    def __init__(self) -> None:
        base_url = "https://bdtd.ibict.br/vufind/api/v1"
        super().__init__(base_url=base_url)

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata from BDTD (Biblioteca Digital de Teses e Dissertações).
        Supports:
          - Direct BDTD IDs (e.g. UFMA_4bd0f7827d06b3ce2d77cabaf6f35327)
          - Prefixed IDs (e.g. bdtd:UFMA_4...)
          - Handle URLs (e.g. https://tedebc.ufma.br/jspui/handle/tede/6900)
          - DOIs (e.g. 10.17771/PUCRio.acad.55901)
        """
        clean_id = identifier.strip()
        if clean_id.lower().startswith("bdtd:"):
            clean_id = clean_id[5:].strip()

        # Check if identifier is a URL or DOI
        is_url = clean_id.startswith("http" + "://") or clean_id.startswith("https://")
        is_doi = "/" in clean_id and "." in clean_id and not is_url

        try:
            fields = _RECORD_FIELDS

            if is_url or is_doi:
                logger.info(f"BDTDAPIClient: Searching for identifier: {clean_id}")
                response = self._get("search", params={"lookfor": clean_id, _FIELD_PARAM: fields})
                data = response.json()
                records = data.get("records", [])
                if not records:
                    logger.info(f"BDTDAPIClient: No BDTD records found for {clean_id}")
                    return None
                record = records[0]
            else:
                logger.info(f"BDTDAPIClient: Fetching record ID: {clean_id}")
                response = self._get("record", params={"id": clean_id, _FIELD_PARAM: fields})
                data = response.json()
                records = data.get("records", [])
                if not records:
                    logger.info(f"BDTDAPIClient: BDTD record ID {clean_id} not found")
                    return None
                record = records[0]

            return self._map_to_research_paper(record)

        except Exception:
            logger.exception(f"BDTDAPIClient: Error fetching metadata for {identifier}")
            return None

    def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> Iterator[ResearchPaper]:
        """
        Free-text/topic search via BDTD's VuFind search endpoint (Issue
        #182), e.g. `import bdtd --query "aprendizado de maquina"`.
        sort_by/sort_order are accepted for interface parity with
        ArxivGateway.search/SearchableMetadataProvider but not honored -
        VuFind's relevance ranking is used as-is. PDF URLs are not resolved
        here (see _map_to_research_paper's resolve_pdf) - that's deferred
        to the async BDTDResolver once an item is actually imported.
        """
        page = 1
        fetched = 0
        while fetched < max_results:
            limit = min(_MAX_PER_PAGE, max_results - fetched)
            try:
                response = self._get(
                    "search",
                    params={
                        "lookfor": query,
                        _FIELD_PARAM: _RECORD_FIELDS,
                        "limit": limit,
                        "page": page,
                    },
                )
                data = response.json()
            except Exception:
                logger.exception(f"BDTDAPIClient: Error searching for '{query}'")
                return

            records = data.get("records", [])
            if not records:
                return

            for record in records:
                yield self._map_to_research_paper(record, resolve_pdf=False)
                fetched += 1
                if fetched >= max_results:
                    return

            page += 1

    def _map_to_research_paper(
        self, item: Dict[str, Any], resolve_pdf: bool = True
    ) -> ResearchPaper:
        # Fields are read in the order the record lists them, so a malformed record fails
        # on the same field it always did.
        title = (item.get("title") or "").strip()
        abstract = self._abstract_of(item)
        authors = self._authors_of(item)
        year = self._first_listed(item.get("publicationDates"))
        publication = self._first_listed(item.get("institutions"))  # the institution
        urls_data = item.get("urls", [])
        url = self._first_url(urls_data)
        extra = self._extra_of(item)

        # Resolve PDF URL (synchronously in BDTDAPIClient). Skipped for bulk
        # search() results (Issue #182): scraping+HEAD-probing every
        # landing page for up to max_results records is too slow/expensive
        # for a search preview - PDF resolution there is deferred to the
        # existing async BDTDResolver, run later via the normal PDF-fetch
        # job pipeline once an item is actually imported.
        pdf_url = None
        if url and resolve_pdf:
            try:
                pdf_url = self._resolve_pdf_url_sync(url)
            except Exception as e:
                logger.warning(f"BDTDAPIClient: Failed to resolve PDF URL for {url}: {e}")

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=year,
            doi=self._doi_of(url, urls_data),
            url=url,
            pdf_url=pdf_url,
            extra=extra,
        )

    @staticmethod
    def _abstract_of(item: Dict[str, Any]) -> str:
        summaries = item.get("summary")
        if summaries and isinstance(summaries, list):
            return "\n\n".join(str(s) for s in summaries if s).strip()
        return ""

    @staticmethod
    def _authors_of(item: Dict[str, Any]) -> list[str]:
        def names(entries: Any) -> list[str]:
            found: list[str] = []
            for a in entries:
                if isinstance(a, str):
                    found.append(a)
                elif isinstance(a, dict):
                    found.extend(a.keys())
            return found

        authors: list[str] = []
        authors_data = item.get("authors", {})
        if isinstance(authors_data, dict):
            for section in ["primary", "secondary"]:
                section_data = authors_data.get(section, {})
                if isinstance(section_data, dict):
                    authors.extend(section_data.keys())
                elif isinstance(section_data, list):
                    authors.extend(names(section_data))
        elif isinstance(authors_data, list):
            authors.extend(names(authors_data))
        return authors

    @staticmethod
    def _first_listed(value: Any) -> Optional[str]:
        """The first entry of a list field as text, when there is one."""
        if value and isinstance(value, list) and value[0]:
            return str(value[0])
        return None

    @staticmethod
    def _first_url(urls_data: Any) -> Optional[str]:
        if not urls_data:
            return None
        first_url = urls_data[0]
        if isinstance(first_url, dict):
            return cast(Optional[str], first_url.get("url"))
        return str(first_url)

    @staticmethod
    def _extra_of(item: Dict[str, Any]) -> Optional[str]:
        """The BDTD-specific fields (degree level, languages, subjects), packed as text."""
        extra_parts = []
        formats = item.get("formats")
        if formats and isinstance(formats, list) and formats[0]:
            extra_parts.append(f"Degree Level: {formats[0]}")

        langs = item.get("languages")
        if langs and isinstance(langs, list) and langs:
            extra_parts.append(f"Languages: {', '.join(langs)}")

        subjects_list = []
        subs = item.get("subjects")
        if subs and isinstance(subs, list):
            for s in subs:
                if isinstance(s, list) and s:
                    subjects_list.append(s[0])
                elif isinstance(s, str):
                    subjects_list.append(s)
        if subjects_list:
            extra_parts.append(f"Subjects: {', '.join(subjects_list)}")

        return "\n".join(extra_parts) if extra_parts else None

    @staticmethod
    def _doi_of(url: Optional[str], urls_data: Any) -> Optional[str]:
        """The DOI in the main URL, else in any of the listed URLs."""
        if url and DOI_ORG in url:
            return url.split(DOI_ORG, 1)[1].strip()
        for url_entry in urls_data:
            entry_url = url_entry.get("url", "") if isinstance(url_entry, dict) else str(url_entry)
            if DOI_ORG in entry_url:
                return entry_url.split(DOI_ORG, 1)[1].strip()
        return None

    def _resolve_pdf_url_sync(self, repo_url: str) -> Optional[str]:
        if repo_url.lower().endswith(".pdf"):
            return repo_url

        try:
            # repo_url comes from harvested repository metadata (untrusted):
            # fetch it through the SSRF guard, with a capped body.
            response = safe_get_text(repo_url, timeout=10)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            base_host = urllib.parse.urlparse(response.url).hostname

            # Extract same-domain links
            links = []
            for a_tag in soup.find_all("a", href=True):
                current_link = urllib.parse.urljoin(str(response.url), str(str(a_tag["href"])))
                # Exact host match: a substring test would also accept
                # e.g. repositorio.example.br.attacker.example.
                same_host = urllib.parse.urlparse(current_link).hostname == base_host
                if same_host and current_link != response.url:
                    links.append(str(current_link))

            # Extract embedded PDF object
            if embedded := soup.find("object", {"type": "application/pdf"}):
                embedded_link = urllib.parse.urljoin(
                    response.url,
                    str(embedded["data"]),
                )
                if str(embedded_link) not in links:
                    links.append(str(embedded_link))

            # Filter downloadable candidate files
            pdf_links = set()
            for u_link in links:
                lower_link = u_link.lower()
                if (
                    lower_link.endswith(".pdf")
                    or "/jspui" in lower_link
                    or "/handle" in lower_link
                    or "/bitstream" in lower_link
                ):
                    # Check if downloadable (HEAD request)
                    try:
                        h = safe_head(
                            u_link,
                            timeout=5,
                            headers={"Referer": u_link, "Accept": "*/*;q=0.8"},
                        )
                        ct = h.headers.get("content-type", "").lower()
                        if ct and "text" not in ct and "html" not in ct:
                            pdf_links.add(u_link)
                    # probing one candidate link; others may still resolve
                    except Exception:  # nosec B112
                        continue

            if not pdf_links:
                return None

            # Calculate Levenshtein similarity to repo URL
            levenshtein_ratios = []
            for link in pdf_links:
                base_url_path, _ = link.rsplit("/", 1)
                ratio = Levenshtein.normalized_similarity(response.url, base_url_path)
                levenshtein_ratios.append((ratio, link))

            if not levenshtein_ratios:
                return None

            max_ratio = max(levenshtein_ratios, key=lambda x: x[0])
            return max_ratio[1]

        except Exception as e:
            logger.debug(f"BDTDAPIClient: Error resolving PDF sync: {e}")
            return None
