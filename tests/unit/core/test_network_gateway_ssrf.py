"""
Issue #235: NetworkGateway must refuse to fetch (or follow a redirect to)
a private/loopback/link-local address, and must not silently trust
follow_redirects. These tests exercise the real validate_public_url logic
(no DNS lookups needed - every URL here uses a literal IP or `localhost`,
which resolve locally without network access) rather than suppressing it
like test_network_gateway.py's unrelated 403/429/redirect-rotation tests.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from zotero_cli.core.services.identity_manager import IdentityManager
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.utils.url_safety import UnsafeURLError


@pytest.fixture
async def gateway():
    gw = NetworkGateway(IdentityManager())
    yield gw
    await gw.close()


@pytest.mark.anyio
async def test_refuses_loopback_url(gateway):
    gateway._client.request = AsyncMock()

    with pytest.raises(UnsafeURLError):
        await gateway.get("http://127.0.0.1/admin")

    gateway._client.request.assert_not_called()


@pytest.mark.anyio
async def test_refuses_private_ip_url(gateway):
    gateway._client.request = AsyncMock()

    with pytest.raises(UnsafeURLError):
        await gateway.get("http://10.0.0.5/internal")

    gateway._client.request.assert_not_called()


@pytest.mark.anyio
async def test_refuses_link_local_metadata_url(gateway):
    """The classic cloud-metadata SSRF target."""
    gateway._client.request = AsyncMock()

    with pytest.raises(UnsafeURLError):
        await gateway.get("http://169.254.169.254/latest/meta-data/")

    gateway._client.request.assert_not_called()


@pytest.mark.anyio
async def test_refuses_non_http_scheme(gateway):
    gateway._client.request = AsyncMock()

    with pytest.raises(UnsafeURLError):
        await gateway.get("file:///etc/passwd")

    gateway._client.request.assert_not_called()


@pytest.mark.anyio
async def test_allows_public_ip_literal(gateway):
    """A URL that validates clean is fetched normally - the guard isn't
    overly broad."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_redirect = False
    gateway._client.request = AsyncMock(return_value=mock_resp)

    response = await gateway.get("http://93.184.216.34/")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_refuses_redirect_to_private_ip(gateway):
    """A validated public URL must not be trusted to redirect wherever it
    wants - each hop is re-validated (Issue #235's core requirement)."""
    redirect_resp = MagicMock(spec=httpx.Response)
    redirect_resp.status_code = 302
    redirect_resp.is_redirect = True
    redirect_resp.headers = {"location": "http://169.254.169.254/latest/meta-data/"}

    gateway._client.request = AsyncMock(return_value=redirect_resp)

    with pytest.raises(UnsafeURLError):
        await gateway.get("http://93.184.216.34/")

    # First hop was fetched (it's a valid public IP), the malicious
    # redirect target was rejected before a second request was made.
    assert gateway._client.request.call_count == 1


@pytest.mark.anyio
async def test_follows_redirect_to_another_public_address(gateway):
    """A redirect to a legitimate public address is still followed."""
    redirect_resp = MagicMock(spec=httpx.Response)
    redirect_resp.status_code = 302
    redirect_resp.is_redirect = True
    redirect_resp.headers = {"location": "http://93.184.216.35/final"}

    final_resp = MagicMock(spec=httpx.Response)
    final_resp.status_code = 200
    final_resp.is_redirect = False

    gateway._client.request = AsyncMock(side_effect=[redirect_resp, final_resp])

    response = await gateway.get("http://93.184.216.34/")
    assert response.status_code == 200
    assert gateway._client.request.call_count == 2
