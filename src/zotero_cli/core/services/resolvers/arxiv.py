import logging
import tempfile
from pathlib import Path
from typing import Optional

from zotero_cli.core.interfaces import PDFResolver
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class ArXivResolver(PDFResolver):
    """
    Resolves PDFs from ArXiv using the ArXiv ID.
    """

    def __init__(self, gateway: NetworkGateway):
        self.gateway = gateway

    async def resolve(self, item: ZoteroItem) -> Optional[Path]:
        arxiv_id = item.arxiv_id
        if not arxiv_id:
            return None

        # ArXiv PDFs are usually at https://arxiv.org/pdf/{id}.pdf
        # Sometimes adding .pdf is not strictly necessary but recommended.
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        try:
            logger.info(f"ArXiv: Attempting to download PDF for {arxiv_id}")
            response = await self.gateway.get(pdf_url)

            # ArXiv sometimes returns a 200 HTML page instead of a PDF if it's a redirect or error
            if "application/pdf" not in response.headers.get("Content-Type", "").lower():
                # Check if it starts with %PDF
                if not response.content.startswith(b"%PDF"):
                    logger.warning(f"ArXiv: URL {pdf_url} did not return a PDF.")
                    return None

            temp_dir = Path(tempfile.gettempdir())
            dest = temp_dir / f"arxiv_{item.key}.pdf"
            dest.write_bytes(response.content)

            logger.info(f"ArXiv: Successfully downloaded PDF for {arxiv_id}")
            return dest
        except Exception as e:
            logger.error(f"ArXiv: Failed to resolve PDF for {arxiv_id}: {e}")
            return None
