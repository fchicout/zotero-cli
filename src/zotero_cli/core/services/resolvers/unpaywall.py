import logging
import tempfile
from pathlib import Path
from typing import Optional

from zotero_cli.core.interfaces import PDFResolver, ResolutionError
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class UnpaywallResolver(PDFResolver):
    """
    Resolves PDFs using the Unpaywall API.
    """

    def __init__(self, gateway: NetworkGateway, email: Optional[str] = None):
        self.gateway = gateway
        self.email = email or "team@zotero-cli.invalid"

    async def resolve(self, item: ZoteroItem) -> Optional[Path]:
        if not item.doi:
            return None

        # Unpaywall requires an email parameter for their "polite pool"
        url = f"https://api.unpaywall.org/v2/{item.doi}?email={self.email}"
        try:
            logger.info(f"Querying Unpaywall for DOI: {item.doi}")
            response = await self.gateway.get(url)
            data = response.json()

            best_location = data.get("best_oa_location")
            if not best_location or not best_location.get("url_for_pdf"):
                logger.info(f"Unpaywall: No OA PDF found for {item.doi}")
                return None

            pdf_url = best_location["url_for_pdf"]
            logger.info(f"Unpaywall: Found OA PDF for {item.doi}: {pdf_url}")

            # Download PDF
            pdf_resp = await self.gateway.get(pdf_url)

            # Save to temp file
            temp_dir = Path(tempfile.gettempdir())
            dest = temp_dir / f"unpaywall_{item.key}.pdf"
            dest.write_bytes(pdf_resp.content)

            return dest
        except Exception as e:
            msg = f"Unpaywall resolution failed for {item.doi}: {e}"
            logger.error(msg)
            raise ResolutionError(msg) from e
