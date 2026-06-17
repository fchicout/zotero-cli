from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_cli.core.services.resolvers.bdtd import BDTDResolver
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    gw = MagicMock()
    gw.get = AsyncMock()
    gw._execute_request = AsyncMock()
    return gw


@pytest.fixture
def thesis_item():
    return ZoteroItem(
        key="BDTD_001",
        version=1,
        item_type="thesis",
        url="https://tedebc.ufma.br/jspui/handle/tede/6900",
    )


@pytest.fixture
def non_thesis_item():
    return ZoteroItem(
        key="JOURNAL_001",
        version=1,
        item_type="journalArticle",
        url="https://example.com/article/12345",
    )


# -- Eligibility Tests -----------------------------------------------------------------


@pytest.mark.anyio
async def test_bdtd_resolver_skips_non_thesis_url(mock_gateway, non_thesis_item):
    """Resolver should return None for non-thesis, non-repo URLs."""
    resolver = BDTDResolver(mock_gateway)
    result = await resolver.resolve(non_thesis_item)
    assert result is None
    mock_gateway.get.assert_not_called()


@pytest.mark.anyio
async def test_bdtd_resolver_skips_no_url(mock_gateway):
    """Resolver should return None when item has no URL."""
    item = ZoteroItem(key="NO_URL", version=1, item_type="thesis", url=None)
    resolver = BDTDResolver(mock_gateway)
    result = await resolver.resolve(item)
    assert result is None


@pytest.mark.anyio
async def test_bdtd_resolver_activates_for_thesis_type(mock_gateway):
    """Resolver should activate for item_type='thesis' even without repo URL markers."""
    item = ZoteroItem(
        key="THESIS_GENERIC",
        version=1,
        item_type="thesis",
        url="https://repositorio.ufrn.br/handle/123456789/12345",
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.url = "https://repositorio.ufrn.br/handle/123456789/12345"
    mock_response.text = "<html><body>No PDF links here</body></html>"

    mock_gateway.get = AsyncMock(return_value=mock_response)

    resolver = BDTDResolver(mock_gateway)
    result = await resolver.resolve(item)
    # Should activate (fetch page) but return None since no PDF links
    assert result is None
    mock_gateway.get.assert_called_once()


# -- Direct PDF URL Test ---------------------------------------------------------------


@pytest.mark.anyio
async def test_bdtd_resolver_direct_pdf_url(mock_gateway):
    """Resolver should download directly when URL ends with .pdf."""
    item = ZoteroItem(
        key="PDF_DIRECT",
        version=1,
        item_type="thesis",
        url="https://tedebc.ufma.br/jspui/bitstream/tede/6900/2/thesis.pdf",
    )
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_response.content = b"%PDF-1.4 bdtd test"

    mock_gateway.get = AsyncMock(return_value=mock_response)

    resolver = BDTDResolver(mock_gateway)
    result = await resolver.resolve(item)

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_bytes() == b"%PDF-1.4 bdtd test"
    result.unlink()


# -- Landing Page Crawling + Levenshtein Scoring Test ----------------------------------


@pytest.mark.anyio
async def test_bdtd_resolver_levenshtein_scoring(mock_gateway, thesis_item):
    """Resolver should select the PDF link with highest Levenshtein similarity."""
    landing_html = """
    <html><body>
        <a href="/jspui/bitstream/tede/6900/2/tese.pdf">Tese PDF</a>
        <a href="/jspui/bitstream/tede/6900/1/license.txt">Licença</a>
        <a href="/jspui/bitstream/tede/9999/1/other.pdf">Other Thesis</a>
    </body></html>
    """
    mock_landing = MagicMock()
    mock_landing.status_code = 200
    mock_landing.url = "https://tedebc.ufma.br/jspui/handle/tede/6900"
    mock_landing.text = landing_html

    # HEAD responses for candidates
    mock_head_pdf_close = MagicMock()
    mock_head_pdf_close.headers = {"content-type": "application/pdf"}

    mock_head_pdf_far = MagicMock()
    mock_head_pdf_far.headers = {"content-type": "application/pdf"}

    # PDF download response
    mock_pdf_response = MagicMock()
    mock_pdf_response.headers = {"Content-Type": "application/pdf"}
    mock_pdf_response.content = b"%PDF-1.5 thesis content"

    mock_gateway._execute_request = AsyncMock(side_effect=[mock_head_pdf_close, mock_head_pdf_far])
    mock_gateway.get = AsyncMock(side_effect=[mock_landing, mock_pdf_response])

    resolver = BDTDResolver(mock_gateway)
    result = await resolver.resolve(thesis_item)

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_bytes() == b"%PDF-1.5 thesis content"
    result.unlink()


# -- Error Handling Test ---------------------------------------------------------------


@pytest.mark.anyio
async def test_bdtd_resolver_non_200_landing_page(mock_gateway, thesis_item):
    """Resolver should return None when the landing page returns non-200."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.url = "https://tedebc.ufma.br/jspui/handle/tede/6900"

    mock_gateway.get = AsyncMock(return_value=mock_response)

    resolver = BDTDResolver(mock_gateway)
    result = await resolver.resolve(thesis_item)
    assert result is None


@pytest.mark.anyio
async def test_bdtd_resolver_invalid_pdf_signature(mock_gateway):
    """Resolver should return None when download does not have %PDF signature."""
    item = ZoteroItem(
        key="INVALID_PDF",
        version=1,
        item_type="thesis",
        url="https://tedebc.ufma.br/jspui/bitstream/tede/1/file.pdf",
    )
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.content = b"<html>Error</html>"

    mock_gateway.get = AsyncMock(return_value=mock_response)

    resolver = BDTDResolver(mock_gateway)
    result = await resolver.resolve(item)
    assert result is None
