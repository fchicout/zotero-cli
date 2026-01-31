from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_cli.core.services.resolvers.generic_scraper import GenericScraperResolver
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def doi_item():
    return ZoteroItem(key="GHI789", version=1, item_type="journalArticle", doi="10.1234/567")

@pytest.mark.anyio
async def test_generic_scraper_success(mock_gateway, doi_item):
    config = {
        "name": "TestScraper",
        "base_url": "http://example.com",
        "query_pattern": "{base_url}/search?doi={doi}",
        "pdf_selector": "a.download-pdf"
    }
    resolver = GenericScraperResolver(mock_gateway, config)

    # Page HTML mock
    mock_html_resp = MagicMock()
    mock_html_resp.status_code = 200
    mock_html_resp.text = '<html><body><a class="download-pdf" href="/files/paper.pdf">Download</a></body></html>'

    # PDF download mock
    mock_pdf_resp = MagicMock()
    mock_pdf_resp.status_code = 200
    mock_pdf_resp.content = b"%PDF-1.4 generic test"
    mock_pdf_resp.headers = {"Content-Type": "application/pdf"}

    mock_gateway.get = AsyncMock(side_effect=[mock_html_resp, mock_pdf_resp])

    result = await resolver.resolve(doi_item)

    assert isinstance(result, Path)
    assert result.name == "generic_TestScraper_GHI789.pdf"
    assert result.read_bytes() == b"%PDF-1.4 generic test"

    # Verify first call URL
    mock_gateway.get.assert_any_call("http://example.com/search?doi=10.1234/567")
    # Verify second call URL (urljoin)
    mock_gateway.get.assert_any_call("http://example.com/files/paper.pdf")

    # Cleanup
    result.unlink()

@pytest.mark.anyio
async def test_generic_scraper_no_selector(mock_gateway, doi_item):
    config = {
        "name": "TestScraper",
        "base_url": "http://example.com",
        "query_pattern": "{base_url}/search?doi={doi}",
        "pdf_selector": "a.not-found"
    }
    resolver = GenericScraperResolver(mock_gateway, config)

    mock_html_resp = MagicMock()
    mock_html_resp.status_code = 200
    mock_html_resp.text = '<html><body><a class="different-class" href="/files/paper.pdf">Download</a></body></html>'

    mock_gateway.get = AsyncMock(return_value=mock_html_resp)

    result = await resolver.resolve(doi_item)
    assert result is None
