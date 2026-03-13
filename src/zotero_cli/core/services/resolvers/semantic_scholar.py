import logging
import tempfile
from pathlib import Path
from typing import Optional

from zotero_cli.core.interfaces import PDFResolver, ResolutionError
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class SemanticScholarResolver(PDFResolver):
    """
    Resolves PDFs using the Semantic Scholar API.
    """

    def __init__(self, gateway: NetworkGateway, api_key: Optional[str] = None):
        self.gateway = gateway
        self.api_key = api_key

    async def resolve(self, item: ZoteroItem) -> Optional[Path]:
        if not item.doi:
            return None

        # Semantic Scholar API endpoint
        url = f"https://api.semanticscholar.org/graph/v1/paper/{item.doi}?fields=isOpenAccess,openAccessPdf"

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            logger.info(f"SemanticScholar: Querying for DOI: {item.doi}")
            response = await self.gateway.get(url, headers=headers)
            data = response.json()

            oa_pdf = data.get("openAccessPdf")
            if not oa_pdf or not oa_pdf.get("url"):
                logger.info(f"SemanticScholar: No OA PDF found for {item.doi}")
                return None

            pdf_url = oa_pdf["url"]
            logger.info(f"SemanticScholar: Found OA PDF for {item.doi}: {pdf_url}")

            # Download PDF
            pdf_resp = await self.gateway.get(pdf_url)

            # Check if it's actually a PDF
            if "application/pdf" not in pdf_resp.headers.get("Content-Type", "").lower():
                if not pdf_resp.content.startswith(b"%PDF"):
                    logger.warning(f"SemanticScholar: URL {pdf_url} did not return a PDF.")
                    return None

            temp_dir = Path(tempfile.gettempdir())
            dest = temp_dir / f"semanticscholar_{item.key}.pdf"
            dest.write_bytes(pdf_resp.content)

            return dest
        except Exception as e:
            msg = f"SemanticScholar: Failed to resolve PDF for {item.doi}: {e}"
            logger.error(msg)
            raise ResolutionError(msg) from e
