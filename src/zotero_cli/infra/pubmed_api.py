import time
import xml.etree.ElementTree as ET
from typing import Optional

import requests

from zotero_cli.core.interfaces import MetadataProvider
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.base_api_client import BaseAPIClient


class PubMedAPIClient(BaseAPIClient, MetadataProvider):
    def __init__(self, api_key: Optional[str] = None):
        # NCBI E-utils base URL
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.api_key = api_key
        super().__init__(base_url=base_url)
        self.last_request_time = 0.0

    def get_paper_metadata(self, identifier: str) -> Optional[ResearchPaper]:
        """
        Retrieves paper metadata for the given identifier (PMID or PMCID).
        """
        self._apply_rate_limit()

        # 1. Resolve PMID if identifier is PMCID
        pmid: Optional[str] = identifier
        if identifier.lower().startswith("pmc"):
            pmid = self._resolve_pmcid_to_pmid(identifier)
            if not pmid:
                return None

        if not pmid:
            return None

        # 2. Fetch full record via efetch
        try:
            params = {
                "db": "pubmed",
                "id": pmid,
                "retmode": "xml"
            }
            if self.api_key:
                params["api_key"] = self.api_key

            response = self._get(endpoint="efetch.fcgi", params=params)
            return self._parse_pubmed_xml(response.text)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"Error fetching PubMed metadata for {pmid}: {e}")
            return None
        except Exception as e:
            print(f"Error parsing PubMed XML for {pmid}: {e}")
            return None

    def _resolve_pmcid_to_pmid(self, pmcid: str) -> Optional[str]:
        """Uses idconv to map PMCID to PMID."""
        try:
            url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
            params = {
                "ids": pmcid,
                "format": "json",
                "tool": "zotero-cli",
                "email": "fchicout@gmail.com"
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            records = data.get("records", [])
            if records and "pmid" in records[0]:
                return str(records[0]["pmid"])
            return None
        except Exception as e:
            print(f"Error converting PMCID {pmcid} to PMID: {e}")
            return None

    def _apply_rate_limit(self):
        """NCBI allows 3 requests/sec without API key, 10 with it."""
        delay = 0.34 if not self.api_key else 0.1
        elapsed = time.time() - self.last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request_time = time.time()

    def _parse_pubmed_xml(self, xml_content: str) -> Optional[ResearchPaper]:
        root = ET.fromstring(xml_content)
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
            year = year[:4] # Extract year from MedlineDate like "2023 Oct-Dec"

        return ResearchPaper(
            title=title,
            abstract=abstract,
            authors=authors,
            publication=journal,
            year=year,
            doi=doi,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{article.findtext('.//PMID')}/"
        )
