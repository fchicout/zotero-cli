"""
Issue #235: unit tests for the shared SSRF guard. Every hostname used
here is a literal IP or `localhost`, resolving without any real network
access, so these tests stay fast and offline like the rest of tests/unit.
"""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import requests

from zotero_cli.core.utils.url_safety import (
    ResponseTooLargeError,
    UnsafeURLError,
    iter_capped_content,
    read_capped_async,
    safe_get,
    validate_public_url,
)


def test_rejects_disallowed_scheme():
    with pytest.raises(UnsafeURLError, match="scheme"):
        validate_public_url("file:///etc/passwd")


def test_rejects_ftp_scheme():
    with pytest.raises(UnsafeURLError, match="scheme"):
        validate_public_url("ftp://93.184.216.34/x")


def test_rejects_loopback():
    with pytest.raises(UnsafeURLError):
        validate_public_url("http://127.0.0.1/")


def test_rejects_localhost():
    with pytest.raises(UnsafeURLError):
        validate_public_url("http://localhost/")


def test_rejects_private_range():
    with pytest.raises(UnsafeURLError):
        validate_public_url("http://10.1.2.3/")
    with pytest.raises(UnsafeURLError):
        validate_public_url("http://192.168.1.1/")


def test_rejects_link_local_metadata_address():
    with pytest.raises(UnsafeURLError):
        validate_public_url("http://169.254.169.254/latest/meta-data/")


def test_rejects_url_with_no_hostname():
    with pytest.raises(UnsafeURLError, match="hostname"):
        validate_public_url("http:///no-host")


def test_allows_public_ip_literal():
    # No real DNS resolution needed - a literal IP is parsed, not looked up.
    validate_public_url("http://93.184.216.34/")  # should not raise


def test_safe_get_refuses_before_any_request_is_made():
    with pytest.raises(UnsafeURLError):
        safe_get("http://127.0.0.1/admin")


def test_safe_get_follows_redirect_and_revalidates_each_hop():
    redirect_resp = MagicMock(spec=requests.Response)
    redirect_resp.is_redirect = True
    redirect_resp.is_permanent_redirect = False
    redirect_resp.headers = {"Location": "http://93.184.216.35/final"}

    final_resp = MagicMock(spec=requests.Response)
    final_resp.is_redirect = False
    final_resp.is_permanent_redirect = False

    mock_session = MagicMock()
    mock_session.get.side_effect = [redirect_resp, final_resp]

    result = safe_get("http://93.184.216.34/", session=mock_session)

    assert result is final_resp
    assert mock_session.get.call_count == 2


def test_safe_get_refuses_redirect_to_private_address():
    redirect_resp = MagicMock(spec=requests.Response)
    redirect_resp.is_redirect = True
    redirect_resp.is_permanent_redirect = False
    redirect_resp.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    mock_session = MagicMock()
    mock_session.get.return_value = redirect_resp

    with pytest.raises(UnsafeURLError):
        safe_get("http://93.184.216.34/", session=mock_session)

    # The first (public) hop was actually fetched; the malicious redirect
    # target was rejected before a second request was made.
    assert mock_session.get.call_count == 1


def test_safe_get_gives_up_after_too_many_redirects():
    loop_resp = MagicMock(spec=requests.Response)
    loop_resp.is_redirect = True
    loop_resp.is_permanent_redirect = False
    loop_resp.headers = {"Location": "http://93.184.216.35/next"}

    mock_session = MagicMock()
    mock_session.get.return_value = loop_resp

    with pytest.raises(UnsafeURLError, match="redirect"):
        safe_get("http://93.184.216.34/", session=mock_session)


def test_gaierror_is_wrapped():
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("name resolution failed")):
        with pytest.raises(UnsafeURLError, match="resolve"):
            validate_public_url("http://this-does-not-resolve.invalid/")


# --- Issue #239: response body size cap ---


def test_iter_capped_content_rejects_declared_oversized_content_length():
    response = MagicMock(spec=requests.Response)
    response.url = "http://93.184.216.34/big.pdf"
    response.headers = {"content-length": "999"}
    response.iter_content.return_value = iter([b"x" * 10])

    with pytest.raises(ResponseTooLargeError, match="Content-Length"):
        list(iter_capped_content(response, max_bytes=100))

    # Rejected before ever touching the stream.
    response.iter_content.assert_not_called()


def test_iter_capped_content_passes_through_within_cap():
    response = MagicMock(spec=requests.Response)
    response.url = "http://93.184.216.34/small.pdf"
    response.headers = {"content-length": "10"}
    response.iter_content.return_value = iter([b"%PDF-1.4", b"..."])

    chunks = list(iter_capped_content(response, max_bytes=100))
    assert b"".join(chunks) == b"%PDF-1.4..."


def test_iter_capped_content_aborts_mid_stream_when_content_length_lies():
    """A hostile server can omit or under-report Content-Length and then
    drip-feed an oversized body - the streaming cutoff must catch that
    even when the upfront header check didn't."""
    response = MagicMock(spec=requests.Response)
    response.url = "http://93.184.216.34/lying.pdf"
    response.headers = {}
    response.iter_content.return_value = iter([b"x" * 50, b"y" * 50, b"z" * 50])

    with pytest.raises(ResponseTooLargeError, match="streaming"):
        list(iter_capped_content(response, max_bytes=80))


@pytest.mark.anyio
async def test_read_capped_async_rejects_declared_oversized_content_length():
    response = MagicMock(spec=httpx.Response)
    response.url = "http://93.184.216.34/big.pdf"
    response.headers = {"content-length": "999"}
    response.aiter_bytes = MagicMock()
    response.aclose = AsyncMock()

    with pytest.raises(ResponseTooLargeError, match="Content-Length"):
        await read_capped_async(response, max_bytes=100)

    response.aiter_bytes.assert_not_called()
    response.aclose.assert_awaited()


@pytest.mark.anyio
async def test_read_capped_async_passes_through_within_cap():
    async def aiter_bytes():
        yield b"%PDF-1.4"
        yield b"..."

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.url = "http://93.184.216.34/small.pdf"
    response.headers = {}
    response.aiter_bytes = MagicMock(return_value=aiter_bytes())
    response.aclose = AsyncMock()
    response.request = httpx.Request("GET", "http://93.184.216.34/small.pdf")

    result = await read_capped_async(response, max_bytes=100)
    assert result.content == b"%PDF-1.4..."
    response.aclose.assert_awaited()


@pytest.mark.anyio
async def test_read_capped_async_aborts_mid_stream_when_content_length_lies():
    async def aiter_bytes():
        yield b"x" * 50
        yield b"y" * 50
        yield b"z" * 50

    response = MagicMock(spec=httpx.Response)
    response.url = "http://93.184.216.34/lying.pdf"
    response.headers = {}
    response.aiter_bytes = MagicMock(return_value=aiter_bytes())
    response.aclose = AsyncMock()

    with pytest.raises(ResponseTooLargeError, match="streaming"):
        await read_capped_async(response, max_bytes=80)

    response.aclose.assert_awaited()
