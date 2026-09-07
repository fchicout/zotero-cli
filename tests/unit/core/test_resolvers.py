from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from zotero_cli.core.services.resolvers.openalex import OpenAlexResolver
from zotero_cli.core.services.resolvers.unpaywall import UnpaywallResolver
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def zotero_item():
    return ZoteroItem(key="ABC123", version=1, item_type="journalArticle", doi="10.1000/123")


@pytest.mark.anyio
async def test_unpaywall_resolver_success(mock_gateway, zotero_item):
    resolver = UnpaywallResolver(mock_gateway)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "best_oa_location": {"url_for_pdf": "http://example.com/paper.pdf"}
    }

    mock_pdf_response = MagicMock()
    mock_pdf_response.content = b"%PDF-1.4 test"

    mock_gateway.get = AsyncMock(side_effect=[mock_response, mock_pdf_response])

    result = await resolver.resolve(zotero_item)

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_bytes() == b"%PDF-1.4 test"

    # Cleanup
    result.unlink()


@pytest.mark.anyio
async def test_openalex_resolver_success(zotero_item):
    from zotero_cli.core.models import ResearchPaper

    mock_client = MagicMock()
    resolver = OpenAlexResolver(mock_client)

    paper = ResearchPaper(
        title="Test Paper",
        abstract="Test Abstract",
        doi="10.1000/123",
        pdf_url="http://example.com/paper.pdf",
    )
    mock_client.get_paper_metadata.return_value = paper

    # Issue #239: safe_async_get now fetches via
    # `client.send(request, stream=True)` and reads the body itself (to
    # enforce a size cap), so the mocked client needs a working
    # `build_request`/`send` pair instead of a plain `.get`.
    async def _aiter_bytes():
        yield b"%PDF-1.4 test alex"

    mock_pdf_response = MagicMock(spec=httpx.Response)
    mock_pdf_response.status_code = 200
    mock_pdf_response.is_redirect = False
    mock_pdf_response.headers = {}
    mock_pdf_response.aiter_bytes = MagicMock(return_value=_aiter_bytes())
    mock_pdf_response.aclose = AsyncMock()
    mock_pdf_response.request = httpx.Request("GET", "http://example.com/paper.pdf")

    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock()
    mock_client_instance.build_request = MagicMock(
        return_value=httpx.Request("GET", "http://example.com/paper.pdf")
    )
    mock_client_instance.send = AsyncMock(return_value=mock_pdf_response)

    # Issue #235: OpenAlexResolver's SSRF guard is exercised in
    # test_network_gateway_ssrf.py / test_resolvers_ssrf.py - this test is
    # about the resolver's happy path, so suppress the real (DNS-hitting)
    # validation for this mocked example.com URL.
    with (
        patch("httpx.AsyncClient", return_value=mock_client_instance),
        patch("zotero_cli.core.utils.url_safety.validate_public_url"),
    ):
        result = await resolver.resolve(zotero_item)

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_bytes() == b"%PDF-1.4 test alex"

    # Cleanup
    result.unlink()


@pytest.mark.anyio
async def test_unpaywall_no_oa(mock_gateway, zotero_item):
    resolver = UnpaywallResolver(mock_gateway)

    mock_response = MagicMock()
    mock_response.json.return_value = {"best_oa_location": None}

    mock_gateway.get = AsyncMock(return_value=mock_response)

    result = await resolver.resolve(zotero_item)
    assert result is None
