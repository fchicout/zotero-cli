from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_cli.core.services.resolvers.arxiv import ArXivResolver
from zotero_cli.core.services.resolvers.semantic_scholar import SemanticScholarResolver
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def arxiv_item():
    return ZoteroItem(key="ABC123", version=1, item_type="journalArticle", arxiv_id="2101.12345")


@pytest.fixture
def doi_item():
    return ZoteroItem(key="DEF456", version=1, item_type="journalArticle", doi="10.1101/456")


@pytest.mark.anyio
async def test_arxiv_resolver_success(mock_gateway, arxiv_item):
    resolver = ArXivResolver(mock_gateway)

    mock_pdf_response = MagicMock()
    mock_pdf_response.status_code = 200
    mock_pdf_response.content = b"%PDF-1.4 arxiv test"
    mock_pdf_response.headers = {"Content-Type": "application/pdf"}

    mock_gateway.get = AsyncMock(return_value=mock_pdf_response)

    result = await resolver.resolve(arxiv_item)

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_bytes() == b"%PDF-1.4 arxiv test"

    # Cleanup
    result.unlink()


@pytest.mark.anyio
async def test_semantic_scholar_resolver_success(mock_gateway, doi_item):
    resolver = SemanticScholarResolver(mock_gateway)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"openAccessPdf": {"url": "http://example.com/ss.pdf"}}

    mock_pdf_response = MagicMock()
    mock_pdf_response.status_code = 200
    mock_pdf_response.content = b"%PDF-1.4 ss test"
    mock_pdf_response.headers = {"Content-Type": "application/pdf"}

    mock_gateway.get = AsyncMock(side_effect=[mock_response, mock_pdf_response])

    result = await resolver.resolve(doi_item)

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_bytes() == b"%PDF-1.4 ss test"

    # Cleanup
    result.unlink()


@pytest.mark.anyio
async def test_arxiv_resolver_no_id(mock_gateway):
    item = ZoteroItem(key="NONE", version=1, item_type="journalArticle")
    resolver = ArXivResolver(mock_gateway)
    result = await resolver.resolve(item)
    assert result is None


@pytest.mark.anyio
async def test_semantic_scholar_no_oa(mock_gateway, doi_item):
    resolver = SemanticScholarResolver(mock_gateway)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"openAccessPdf": None}

    mock_gateway.get = AsyncMock(return_value=mock_response)

    result = await resolver.resolve(doi_item)
    assert result is None
