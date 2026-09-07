from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from zotero_cli.core.exceptions import RetryableError
from zotero_cli.core.services.identity_manager import IdentityManager
from zotero_cli.core.services.network_gateway import NetworkGateway


def make_stream_response(status_code, is_redirect=False, headers=None, body=b""):
    """Issue #239: NetworkGateway now fetches via `client.send(request,
    stream=True)` and reads the body itself (to enforce a size cap), so a
    mocked response needs a working async `aiter_bytes`/`aclose` rather
    than a pre-populated `.content`."""

    async def _aiter_bytes():
        if body:
            yield body

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.is_redirect = is_redirect
    mock_resp.headers = headers or {}
    mock_resp.aiter_bytes = MagicMock(return_value=_aiter_bytes())
    mock_resp.aclose = AsyncMock()
    mock_resp.request = httpx.Request("GET", "http://example.com")
    return mock_resp


@pytest.fixture
def identity_manager():
    return IdentityManager()


@pytest.fixture
async def gateway(identity_manager):
    gw = NetworkGateway(identity_manager)
    yield gw
    await gw.close()


@pytest.fixture(autouse=True)
def no_ssrf_check():
    """These tests exercise 403/429/redirect-rotation behavior, not the
    SSRF guard itself (Issue #235, covered by test_network_gateway_ssrf.py)
    - suppress it here so this file's mocked `example.com` URLs don't
    trigger a real DNS lookup."""
    with patch("zotero_cli.core.services.network_gateway.validate_public_url"):
        yield


@pytest.mark.anyio
async def test_successful_request(gateway):
    mock_resp = make_stream_response(200)
    gateway._client.send = AsyncMock(return_value=mock_resp)
    original_build_request = gateway._client.build_request
    gateway._client.build_request = MagicMock(side_effect=original_build_request)

    response = await gateway.get("http://example.com")
    assert response.status_code == 200

    # Verify User-Agent was injected
    call_args = gateway._client.build_request.call_args
    assert "User-Agent" in call_args.kwargs["headers"]


@pytest.mark.anyio
async def test_rate_limit_429(gateway):
    mock_resp = make_stream_response(429, headers={"Retry-After": "120"})
    gateway._client.send = AsyncMock(return_value=mock_resp)

    with pytest.raises(RetryableError) as exc:
        await gateway.get("http://example.com")

    assert exc.value.retry_after == 120


@pytest.mark.anyio
async def test_soft_block_403_rotation(gateway):
    # First call 403, Second call 200
    mock_resp_403 = make_stream_response(403)
    mock_resp_200 = make_stream_response(200)

    gateway._client.send = AsyncMock(side_effect=[mock_resp_403, mock_resp_200])

    # Capture initial identity
    initial_ua = gateway.identity_manager.get_current_identity()

    response = await gateway.get("http://example.com")
    assert response.status_code == 200

    # Verify two calls were made
    assert gateway._client.send.call_count == 2

    # Verify identity was rotated
    final_ua = gateway.identity_manager.get_current_identity()
    assert initial_ua != final_ua


@pytest.mark.anyio
async def test_persistent_403_with_no_auth_header_raises_generic_http_error(gateway):
    """A persistent 403 with only a User-Agent header (no API key) is a
    generic bot-block, not a bad-credential signal - unchanged behavior."""
    mock_resp_403 = make_stream_response(403)
    gateway._client.send = AsyncMock(return_value=mock_resp_403)

    with pytest.raises(httpx.HTTPStatusError):
        await gateway.get("http://example.com")


@pytest.mark.anyio
async def test_persistent_403_with_api_key_header_raises_clear_error(gateway):
    """Issue #223: a persistent 403 with an API key/auth header present
    (e.g. x-api-key for Semantic Scholar) means the credential itself is
    likely invalid - identity rotation can't fix that, so this must fail
    fast with an actionable message, not a generic HTTPStatusError."""
    mock_resp_403 = make_stream_response(403)
    gateway._client.send = AsyncMock(return_value=mock_resp_403)

    with pytest.raises(ValueError, match="x-api-key"):
        await gateway.get("http://example.com", headers={"x-api-key": "bad-key"})


@pytest.mark.anyio
async def test_response_over_size_cap_is_rejected(gateway):
    """Issue #239: a response body exceeding the size cap must be aborted
    mid-stream rather than fully buffered into memory - exercised through
    the real streaming/cutoff logic (a low max_bytes stands in for the
    real 50MB cap, so the test doesn't need a huge payload)."""
    from zotero_cli.core.utils.url_safety import ResponseTooLargeError, read_capped_async

    async def capped_at_4_bytes(response):
        return await read_capped_async(response, max_bytes=4)

    mock_resp = make_stream_response(200, body=b"x" * 10)
    gateway._client.send = AsyncMock(return_value=mock_resp)

    with patch(
        "zotero_cli.core.services.network_gateway.read_capped_async",
        side_effect=capped_at_4_bytes,
    ):
        with pytest.raises(ResponseTooLargeError):
            await gateway.get("http://example.com")

    mock_resp.aclose.assert_awaited()
