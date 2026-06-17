# mypy: ignore-errors
import logging
import urllib.parse
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup
from rapidfuzz.distance import Levenshtein

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

DOI_ORG = "doi.org/"



class BDTDAPIClient(BaseAPIClient, MetadataProvider):
    def __init__(self):
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
            fields = [
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

            if is_url or is_doi:
                logger.info(f"BDTDAPIClient: Searching for identifier: {clean_id}")
                response = self._get("search", params={"lookfor": clean_id, "field[]": fields})
                data = response.json()
                records = data.get("records", [])
                if not records:
                    logger.info(f"BDTDAPIClient: No BDTD records found for {clean_id}")
                    return None
                record = records[0]
            else:
                logger.info(f"BDTDAPIClient: Fetching record ID: {clean_id}")
                response = self._get("record", params={"id": clean_id, "field[]": fields})
                data = response.json()
                records = data.get("records", [])
                if not records:
                    logger.info(f"BDTDAPIClient: BDTD record ID {clean_id} not found")
                    return None
                record = records[0]

            return self._map_to_research_paper(record)

        except Exception as e:
            logger.error(f"BDTDAPIClient: Error fetching metadata for {identifier}: {e}")
            return None

    def _map_to_research_paper(self, item: Dict[str, Any]) -> ResearchPaper:
        # Title
        title = (item.get("title") or "").strip()

        # Abstract (from summary field list)
        abstract = ""
        summaries = item.get("summary")
        if summaries and isinstance(summaries, list):
            abstract = "\n\n".join(str(s) for s in summaries if s).strip()

        # Authors
        authors: list[str] = []
        authors_data = item.get("authors", {})
        if isinstance(authors_data, dict):
            for section in ["primary", "secondary"]:
                section_data = authors_data.get(section, {})
                if isinstance(section_data, dict):
                    authors.extend(section_data.keys())
                elif isinstance(section_data, list):
                    for a in section_data:
                        if isinstance(a, str):
                            authors.append(a)
                        elif isinstance(a, dict):
                            authors.extend(a.keys())
        elif isinstance(authors_data, list):
            for a in authors_data:
                if isinstance(a, str):
                    authors.append(a)
                elif isinstance(a, dict):
                    authors.extend(a.keys())

        # Year
        year = None
        pub_dates = item.get("publicationDates")
        if pub_dates and isinstance(pub_dates, list) and pub_dates[0]:
            year = str(pub_dates[0])

        # Institution (mapped to publication)
        publication = None
        insts = item.get("institutions")
        if insts and isinstance(insts, list) and insts[0]:
            publication = str(insts[0])

        # URL
        url = None
        urls_data = item.get("urls", [])
        if urls_data:
            first_url = urls_data[0]
            if isinstance(first_url, dict):
                url = first_url.get("url")
            else:
                url = str(first_url)

        # Packed extra BDTD-specific fields
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

        extra = "\n".join(extra_parts) if extra_parts else None

        # Resolve PDF URL (synchronously in BDTDAPIClient)
        pdf_url = None
        if url:
            try:
                pdf_url = self._resolve_pdf_url_sync(url)
            except Exception as e:
                logger.warning(f"BDTDAPIClient: Failed to resolve PDF URL for {url}: {e}")

        # Check for DOI inside urls_data or url string
        doi = None
        if url and DOI_ORG in url:
            doi = url.split(DOI_ORG, 1)[1].strip()
        else:
            for url_entry in urls_data:
                entry_url = (
                    url_entry.get("url", "") if isinstance(url_entry, dict) else str(url_entry)
                )
                if DOI_ORG in entry_url:
                    doi = entry_url.split(DOI_ORG, 1)[1].strip()
                    break

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=publication,
            year=year,
            doi=doi,
            url=url,
            pdf_url=pdf_url,
            extra=extra,
        )

    def _resolve_pdf_url_sync(self, repo_url: str) -> Optional[str]:
        if repo_url.lower().endswith(".pdf"):
            return repo_url

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0"
            }
            # Fetch landing page
            response = requests.get(repo_url, allow_redirects=True, timeout=10, headers=headers)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            base_parsed = urllib.parse.urlparse(response.url)
            base_url = base_parsed.netloc

            # Extract same-domain links
            links = []
            for a_tag in soup.find_all("a", href=True):
                current_link = urllib.parse.urljoin(str(response.url), str(str(a_tag["href"])))
                if base_url in current_link and current_link != response.url:
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
                        h = requests.head(
                            u_link,
                            allow_redirects=True,
                            timeout=5,
                            headers={**headers, "Referer": u_link, "Accept": "*/*;q=0.8"},
                        )
                        ct = h.headers.get("content-type", "").lower()
                        if ct and "text" not in ct and "html" not in ct:
                            pdf_links.add(u_link)
                    except Exception:
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
