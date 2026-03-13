import logging
import tempfile
from pathlib import Path
from typing import Optional

from zotero_cli.core.interfaces import PDFResolver, ResolutionError
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class OpenAlexResolver(PDFResolver):
    """
    Resolves PDFs using the OpenAlex API.
    """

    def __init__(self, gateway: NetworkGateway):
        self.gateway = gateway

    async def resolve(self, item: ZoteroItem) -> Optional[Path]:
        if not item.doi:
            return None

        # OpenAlex uses doi: prefix
        url = f"https://api.openalex.org/works/doi:{item.doi}"
        try:
            logger.info(f"Querying OpenAlex for DOI: {item.doi}")
            response = await self.gateway.get(url)
            data = response.json()

            oa_info = data.get("open_access", {})
            if not oa_info.get("is_oa"):
                logger.info(f"OpenAlex: Work {item.doi} is not Open Access.")
                return None

            best_location = data.get("best_oa_location")
            if not best_location or not best_location.get("pdf_url"):
                logger.info(f"OpenAlex: No direct PDF URL found for {item.doi}")
                return None

            pdf_url = best_location["pdf_url"]
            logger.info(f"OpenAlex: Found OA PDF for {item.doi}: {pdf_url}")

            # Download PDF
            pdf_resp = await self.gateway.get(pdf_url)

            # Save to temp file
            temp_dir = Path(tempfile.gettempdir())
            dest = temp_dir / f"openalex_{item.key}.pdf"
            dest.write_bytes(pdf_resp.content)

            return dest
        except Exception as e:
            msg = f"OpenAlex resolution failed for {item.doi}: {e}"
            logger.error(msg)
            raise ResolutionError(msg) from e
