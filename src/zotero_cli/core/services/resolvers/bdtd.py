# mypy: ignore-errors
import logging
import tempfile
import urllib.parse
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from rapidfuzz.distance import Levenshtein

from zotero_cli.core.interfaces import PDFResolver, ResolutionError
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class BDTDResolver(PDFResolver):
    """
    Asynchronously resolves thesis PDFs from BDTD and institutional repositories
    using BeautifulSoup scraping and Levenshtein-based scoring.
    """

    def __init__(self, gateway: NetworkGateway):
        self.gateway = gateway

    async def resolve(self, item: ZoteroItem) -> Optional[Path]:
        repo_url = item.url
        if not repo_url:
            return None

        # Check if the URL points to an academic repository or item is a thesis
        is_thesis = item.item_type == "thesis"
        is_repo_url = any(
            x in repo_url.lower() for x in ["handle", "jspui", "tede", "bitstream", "bdtd.ibict.br"]
        )

        if not (is_thesis or is_repo_url):
            return None

        # If repo_url itself ends with .pdf, download directly
        if repo_url.lower().endswith(".pdf"):
            return await self._download_pdf(repo_url, item.key)

        try:
            logger.info(f"BDTDResolver: Attempting to resolve PDF from landing page: {repo_url}")
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0"
            }

            # Fetch the landing page
            response = await self.gateway.get(repo_url, headers=headers)
            if response.status_code != 200:
                logger.warning(
                    f"BDTDResolver: Failed to fetch {repo_url}, status: {response.status_code}"
                )
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            base_parsed = urllib.parse.urlparse(str(response.url))
            base_domain = base_parsed.netloc

            # Extract same-domain links
            links = []
            for a_tag in soup.find_all("a", href=True):
                current_link = urllib.parse.urljoin(str(response.url), str(str(a_tag["href"])))
                current_parsed = urllib.parse.urlparse(current_link)
                if base_domain in current_parsed.netloc and current_link != str(response.url):
                    links.append(str(current_link))

            # Extract embedded PDF object
            if embedded := soup.find("object", {"type": "application/pdf"}):
                embedded_link = urllib.parse.urljoin(
                    str(response.url),
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
                        h = await self.gateway._execute_request(
                            "HEAD",
                            u_link,
                            headers={**headers, "Referer": u_link, "Accept": "*/*;q=0.8"},
                            timeout=5,
                        )
                        ct = h.headers.get("content-type", "").lower()
                        if ct and "text" not in ct and "html" not in ct:
                            pdf_links.add(u_link)
                    except Exception:
                        continue

            if not pdf_links:
                logger.info(f"BDTDResolver: No PDF links resolved on landing page {repo_url}")
                return None

            # Calculate Levenshtein similarity to repo URL
            levenshtein_ratios = []
            for link in pdf_links:
                if "/" in link:
                    base_url_path, _ = link.rsplit("/", 1)
                else:
                    base_url_path = link
                ratio = Levenshtein.normalized_similarity(str(response.url), base_url_path)
                levenshtein_ratios.append((ratio, link))

            if not levenshtein_ratios:
                return None

            max_ratio = max(levenshtein_ratios, key=lambda x: x[0])
            resolved_pdf_url = max_ratio[1]
            logger.info(
                f"BDTDResolver: Selected best PDF URL {resolved_pdf_url} with ratio {max_ratio[0]}"
            )

            return await self._download_pdf(resolved_pdf_url, item.key)

        except Exception as e:
            msg = f"BDTDResolver: Failed to resolve PDF for {item.key}: {e}"
            logger.error(msg)
            raise ResolutionError(msg) from e

    async def _download_pdf(self, pdf_url: str, item_key: str) -> Optional[Path]:
        try:
            logger.info(f"BDTDResolver: Downloading PDF: {pdf_url}")
            response = await self.gateway.get(pdf_url)

            # Verify %PDF header or Content-Type
            if "application/pdf" not in response.headers.get("Content-Type", "").lower():
                if not response.content.startswith(b"%PDF"):
                    logger.warning(
                        f"BDTDResolver: URL {pdf_url} did not return a valid PDF signature."
                    )
                    return None

            temp_dir = Path(tempfile.gettempdir())
            dest = temp_dir / f"bdtd_{item_key}.pdf"
            dest.write_bytes(response.content)
            logger.info(f"BDTDResolver: Successfully downloaded PDF to {dest}")
            return dest
        except Exception as e:
            logger.error(f"BDTDResolver: Download failed for {pdf_url}: {e}")
            return None
