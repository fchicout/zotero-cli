import logging
import re
import time
from typing import Dict, Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.utils.normalization import is_valid_doi, normalize_doi
from zotero_cli.infra.base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

_PMID_RE = re.compile(r"^\d{1,9}$")
_PMCID_RE = re.compile(r"^pmc\d+$", re.IGNORECASE)


class PubMedAPIClient(BaseAPIClient, MetadataProvider):
    def __init__(self, api_key: Optional[str] = None, contact_email: Optional[str] = None):
        # NCBI E-utils base URL
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.api_key = api_key
        self.contact_email = contact_email
        # min_request_interval=0: this client already self-throttles more
        # precisely via _apply_rate_limit() below (API-key-aware: 3 vs 10
        # req/s), so the base class's generic pacing would be redundant.
        super().__init__(base_url=base_url, min_request_interval=0)
        self.last_request_time = 0.0

    def _ncbi_params(self) -> Dict[str, str]:
        """NCBI asks tools to identify themselves; the contact email is the
        user's own configured one, sent only if set (Issue #337)."""
        params = {"tool": "zotero-cli"}
        if self.contact_email:
            params["email"] = self.contact_email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata for a PMID, a PMCID, or a DOI.

        efetch only understands PMIDs, and NCBI reads anything else loosely:
        sent a DOI like "10.1145/...", it returns PMID 10, an unrelated
        paper (Issue #340). So DOIs are first looked up with esearch's
        [doi] field, the fetched record's DOI must match, and any other
        identifier is ignored.
        """
        identifier = identifier.strip()
        queried_doi: Optional[str] = None
        pmid: Optional[str]
        if _PMID_RE.match(identifier):
            pmid = identifier
        elif _PMCID_RE.match(identifier):
            self._apply_rate_limit()
            pmid = self._resolve_pmcid_to_pmid(identifier)
        elif is_valid_doi(normalize_doi(identifier)):
            queried_doi = normalize_doi(identifier)
            self._apply_rate_limit()
            pmid = self._resolve_doi_to_pmid(queried_doi)
        else:
            return None

        if not pmid:
            return None

        self._apply_rate_limit()
        try:
            params = {"db": "pubmed", "id": pmid, "retmode": "xml", **self._ncbi_params()}
            response = self._get(endpoint="efetch.fcgi", params=params)
            paper = self._parse_pubmed_xml(response.text)
            if (
                paper is not None
                and queried_doi is not None
                and (not paper.doi or normalize_doi(paper.doi).lower() != queried_doi.lower())
            ):
                logger.info(f"PubMedAPIClient: PMID {pmid} is not the record for DOI {queried_doi}")
                return None
            return paper

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            logger.exception(f"PubMedAPIClient: Error fetching metadata for {pmid}")
            return None
        except Exception:
            logger.exception(f"PubMedAPIClient: Error parsing XML for {pmid}")
            return None

    def _resolve_doi_to_pmid(self, doi: str) -> Optional[str]:
        """Finds the PMID indexed under `doi`, if exactly one."""
        try:
            params = {
                "db": "pubmed",
                "term": f'"{doi}"[doi]',
                "retmode": "json",
                **self._ncbi_params(),
            }
            response = self._get(endpoint="esearch.fcgi", params=params)
            ids = response.json().get("esearchresult", {}).get("idlist", [])
            return str(ids[0]) if len(ids) == 1 else None
        except Exception:
            logger.exception(f"PubMedAPIClient: Error looking up DOI {doi}")
            return None

    def _resolve_pmcid_to_pmid(self, pmcid: str) -> Optional[str]:
        """Uses idconv to map PMCID to PMID."""
        try:
            url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
            params = {"ids": pmcid, "format": "json", **self._ncbi_params()}
            params.pop("api_key", None)  # idconv doesn't take an API key
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            records = data.get("records", [])
            if records and "pmid" in records[0]:
                return str(records[0]["pmid"])
            return None
        except Exception:
            logger.exception(f"PubMedAPIClient: Error converting PMCID {pmcid} to PMID")
            return None

    def _apply_rate_limit(self) -> None:
        """NCBI allows 3 requests/sec without API key, 10 with it."""
        delay = 0.34 if not self.api_key else 0.1
        elapsed = time.time() - self.last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request_time = time.time()

    def _parse_pubmed_xml(self, xml_content: str) -> Optional[ResearchPaper]:
        import defusedxml.ElementTree as DET

        root = DET.fromstring(xml_content)
        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        # Title
        title_node = article.find(".//ArticleTitle")
        title = "".join(title_node.itertext()) if title_node is not None else ""

        # Abstract
        abstract_parts = []
        for abs_text in article.findall(".//AbstractText"):
            label = abs_text.get("Label")
            text = "".join(abs_text.itertext())
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = "\n\n".join(abstract_parts)

        # Authors
        authors = []
        for author in article.findall(".//Author"):
            last_name = author.findtext("LastName")
            fore_name = author.findtext("ForeName")
            initials = author.findtext("Initials")

            if last_name and (fore_name or initials):
                name = f"{fore_name or initials} {last_name}"
                authors.append(name)
            else:
                collective = author.findtext("CollectiveName")
                if collective:
                    authors.append(collective)

        # DOI
        doi = None
        for id_node in article.findall(".//ArticleId"):
            if id_node.get("IdType") == "doi":
                doi = id_node.text
                break

        # Publication
        journal = article.findtext(".//Title") or article.findtext(".//ISOAbbreviation") or ""

        # Year
        year = article.findtext(".//PubDate/Year") or article.findtext(".//PubDate/MedlineDate")
        if year and len(year) > 4:
            year = year[:4]  # Extract year from MedlineDate like "2023 Oct-Dec"

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=journal,
            year=year,
            doi=doi,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{article.findtext('.//PMID')}/",
        )
