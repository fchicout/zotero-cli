import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from zotero_cli.core.interfaces import PDFResolver
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class GenericScraperResolver(PDFResolver):
    """
    Generic PDF resolver that scrapes a webpage based on YAML configuration.
    """

    def __init__(self, gateway: NetworkGateway, config: Dict):
        self.gateway = gateway
        self.name = config.get("name", "GenericScraper")
        self.base_url = config.get("base_url")
        self.query_pattern = config.get("query_pattern")
        self.pdf_selector = config.get("pdf_selector")
        self.follow_redirects = config.get("follow_redirects", True)

    async def resolve(self, item: ZoteroItem) -> Optional[Path]:
        if not self.query_pattern:
            return None

        if not item.doi and "{doi}" in self.query_pattern:
            return None

        if not self.pdf_selector:
            return None

        # 1. Construct URL
        query_url = self.query_pattern.format(
            base_url=self.base_url, doi=item.doi, arxiv_id=item.arxiv_id, key=item.key
        )

        try:
            logger.info(f"{self.name}: Querying {query_url}")

            # 2. Fetch page HTML
            response = await self.gateway.get(query_url)
            html = response.text

            # 3. Parse HTML
            soup = BeautifulSoup(html, "html.parser")

            # 4. Extract PDF link
            link_tag = soup.select_one(self.pdf_selector)
            if not link_tag:
                logger.info(
                    f"{self.name}: PDF selector '{self.pdf_selector}' not found on {query_url}"
                )
                return None

            pdf_url = link_tag.get("href")
            if not pdf_url:
                logger.info(f"{self.name}: Found selector but no href on {query_url}")
                return None

            # 5. Resolve relative links
            pdf_url = urljoin(query_url, pdf_url)
            logger.info(f"{self.name}: Found PDF URL: {pdf_url}")

            # 6. Download PDF
            pdf_resp = await self.gateway.get(pdf_url)

            # Validation
            if "application/pdf" not in pdf_resp.headers.get("Content-Type", "").lower():
                if not pdf_resp.content.startswith(b"%PDF"):
                    logger.warning(f"{self.name}: URL {pdf_url} did not return a PDF.")
                    return None

            temp_dir = Path(tempfile.gettempdir())
            dest = temp_dir / f"generic_{self.name}_{item.key}.pdf"
            dest.write_bytes(pdf_resp.content)

            return dest

        except Exception as e:
            logger.error(f"{self.name}: Failed to resolve PDF for {item.key}: {e}")
            return None
