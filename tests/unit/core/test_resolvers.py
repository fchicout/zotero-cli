from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
async def test_openalex_resolver_success(mock_gateway, zotero_item):
    resolver = OpenAlexResolver(mock_gateway)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "open_access": {"is_oa": True},
        "best_oa_location": {"pdf_url": "http://example.com/paper.pdf"}
    }

    mock_pdf_response = MagicMock()
    mock_pdf_response.content = b"%PDF-1.4 test alex"

    mock_gateway.get = AsyncMock(side_effect=[mock_response, mock_pdf_response])

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
