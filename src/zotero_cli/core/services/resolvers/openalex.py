import logging
import tempfile
from pathlib import Path
from typing import Optional

import requests

from zotero_cli.core.interfaces import PDFResolver, ResolutionError
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.openalex_api import OpenAlexAPIClient

logger = logging.getLogger(__name__)


class OpenAlexResolver(PDFResolver):
    """
    Resolves PDFs using the OpenAlex API Client.
    """

    def __init__(self, client: OpenAlexAPIClient):
        self.client = client

    async def resolve(self, item: ZoteroItem) -> Optional[Path]:
        if not item.doi:
            return None

        try:
            logger.info(f"Querying OpenAlex for DOI: {item.doi}")
            paper = self.client.get_paper_metadata(item.doi)

            if not paper or not paper.pdf_url:
                logger.info(f"OpenAlex: No Open Access PDF found for {item.doi}")
                return None

            pdf_url = paper.pdf_url
            logger.info(f"OpenAlex: Found OA PDF for {item.doi}: {pdf_url}")

            # Download PDF - OpenAlexAPIClient._get is synchronous but we are in async resolve.
            # However, MetadataProvider interface is currently synchronous.
            # We'll use requests directly for the download to keep it simple, or use client._get
            # but resolve is async so we might want to keep the async nature if possible.
            # But the existing code used await self.gateway.get(pdf_url).
            # Let's keep it consistent with other resolvers if they use gateway.

            # Actually, the blueprint says "use the new OpenAlexAPIClient instead of making direct raw requests".
            # I'll use requests here for the binary download as the client is for metadata.

            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()

            # Save to temp file
            temp_dir = Path(tempfile.gettempdir())
            dest = temp_dir / f"openalex_{item.key}.pdf"
            dest.write_bytes(response.content)

            return dest
        except Exception as e:
            msg = f"OpenAlex resolution failed for {item.doi}: {e}"
            logger.error(msg)
            raise ResolutionError(msg) from e
