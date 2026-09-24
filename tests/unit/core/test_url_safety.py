"""
Issue #235: unit tests for the shared SSRF guard. Every hostname used
here is a literal IP or `localhost`, resolving without any real network
access, so these tests stay fast and offline like the rest of tests/unit.
"""

import gzip
import socket
import zlib
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
    mock_session.request.side_effect = [redirect_resp, final_resp]

    result = safe_get("http://93.184.216.34/", session=mock_session)

    assert result is final_resp
    assert mock_session.request.call_count == 2


def test_safe_get_refuses_redirect_to_private_address():
    redirect_resp = MagicMock(spec=requests.Response)
    redirect_resp.is_redirect = True
    redirect_resp.is_permanent_redirect = False
    redirect_resp.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    mock_session = MagicMock()
    mock_session.request.return_value = redirect_resp

    with pytest.raises(UnsafeURLError):
        safe_get("http://93.184.216.34/", session=mock_session)

    # The first (public) hop was actually fetched; the malicious redirect
    # target was rejected before a second request was made.
    assert mock_session.request.call_count == 1


def test_safe_get_gives_up_after_too_many_redirects():
    loop_resp = MagicMock(spec=requests.Response)
    loop_resp.is_redirect = True
    loop_resp.is_permanent_redirect = False
    loop_resp.headers = {"Location": "http://93.184.216.35/next"}

    mock_session = MagicMock()
    mock_session.request.return_value = loop_resp

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


async def _read_through_real_client(encoding, body):
    """Streams `body` through a real httpx.AsyncClient (not a mock), so
    httpx's actual Content-Encoding decoding runs the way it does in
    production."""

    def handler(request):
        return httpx.Response(
            200,
            headers={"Content-Encoding": encoding, "Content-Type": "application/json"},
            content=body,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        request = client.build_request("GET", "http://93.184.216.34/works/x")
        response = await client.send(request, stream=True)
        return await read_capped_async(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "encoding, compress",
    [
        ("gzip", gzip.compress),
        ("deflate", zlib.compress),
    ],
)
async def test_read_capped_async_does_not_decompress_twice(encoding, compress):
    """Regression test for Issue #321: aiter_bytes() already decodes a
    compressed body, so the rebuilt response must not keep advertising
    Content-Encoding - otherwise httpx decodes the plain bytes again and
    raises "Error -3 while decompressing data: incorrect header check"."""
    payload = b'{"message": {"reference": [{"DOI": "10.1/x"}]}}'

    result = await _read_through_real_client(encoding, compress(payload))

    assert result.json() == {"message": {"reference": [{"DOI": "10.1/x"}]}}
    assert "content-encoding" not in result.headers
    assert result.headers["content-length"] == str(len(payload))
    assert result.headers["content-type"] == "application/json"


# --- is_global coverage (CGNAT, IPv4-mapped IPv6, ...) ---------------------


@pytest.mark.parametrize(
    "address",
    [
        "100.64.0.1",  # CGNAT / Tailscale
        "100.100.100.200",  # a cloud metadata address inside CGNAT
        "192.88.99.1",  # 6to4 relay anycast
        "fec0::1",  # deprecated site-local IPv6
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::ffff:10.0.0.1",  # IPv4-mapped private
        "224.0.0.1",  # multicast
        "0.0.0.0",
        "169.254.169.254",
    ],
)
def test_non_global_addresses_are_rejected(address):
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", (address, 0))]):
        with pytest.raises(UnsafeURLError):
            validate_public_url("http://example.com/x.pdf")


def test_global_address_is_accepted():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        validate_public_url("http://example.com/x.pdf")


def test_any_non_public_address_among_several_is_rejected():
    infos = [(2, 1, 6, "", ("93.184.216.34", 0)), (2, 1, 6, "", ("127.0.0.1", 0))]
    with patch("socket.getaddrinfo", return_value=infos):
        with pytest.raises(UnsafeURLError):
            validate_public_url("http://example.com/")


# --- Connection pinning ------------------------------------------------------


def test_requests_connection_connects_to_the_validated_address():
    """The address checked is the one connected to: a second DNS answer
    (e.g. a zero-TTL rebinding to 127.0.0.1) never reaches the socket."""
    from zotero_cli.core.utils import url_safety

    answers = iter(
        [
            [(2, 1, 6, "", ("93.184.216.34", 0))],  # validation lookup
            [(2, 1, 6, "", ("127.0.0.1", 0))],  # what a rebinding server would say next
        ]
    )
    conn = url_safety._PinnedHTTPConnection("example.com", 80)
    with (
        patch("socket.getaddrinfo", side_effect=lambda *a, **k: next(answers)),
        patch("urllib3.connection.connection.create_connection") as create,
    ):
        conn._new_conn()
    assert create.call_args.args[0] == ("93.184.216.34", 80)
    assert conn.host == "example.com"  # Host header and TLS name unchanged


def test_requests_connection_refuses_a_non_public_answer():
    from zotero_cli.core.utils import url_safety

    conn = url_safety._PinnedHTTPSConnection("example.com", 443)
    with (
        patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.5", 0))]),
        patch("urllib3.connection.connection.create_connection") as create,
    ):
        with pytest.raises(UnsafeURLError):
            conn._new_conn()
    create.assert_not_called()


def test_public_only_session_mounts_pinned_pools():
    from zotero_cli.core.utils import url_safety

    session = url_safety.public_only_session()
    adapter = session.get_adapter("https://example.com/")
    assert isinstance(adapter, url_safety.PublicOnlyAdapter)
    assert adapter.poolmanager.pool_classes_by_scheme["https"] is url_safety._PinnedHTTPSConnectionPool


@pytest.mark.anyio
async def test_httpx_client_is_pinned_and_refuses_non_public_answer():
    """Guards against httpx internals changing under pin_public_ips: a real
    AsyncClient must end up with the public-only backend."""
    import httpx

    from zotero_cli.core.utils import url_safety

    client = url_safety.pin_public_ips(httpx.AsyncClient())
    pool = client._transport._pool  # type: ignore[attr-defined]
    assert isinstance(pool._network_backend, url_safety._PublicOnlyAsyncBackend)
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))]):
        with pytest.raises(UnsafeURLError):
            await pool._network_backend.connect_tcp("example.com", 443)
    await client.aclose()


@pytest.mark.anyio
async def test_httpx_backend_connects_to_the_validated_address():
    from unittest.mock import AsyncMock

    from zotero_cli.core.utils import url_safety

    inner = AsyncMock()
    backend = url_safety._PublicOnlyAsyncBackend(inner)
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        await backend.connect_tcp("example.com", 443, timeout=5)
    assert inner.connect_tcp.call_args.args[:2] == ("93.184.216.34", 443)


# --- HEAD, capped text, PDF signature -----------------------------------------


def test_safe_head_validates_redirect_hops():
    redirect_resp = MagicMock(spec=requests.Response)
    redirect_resp.is_redirect = True
    redirect_resp.is_permanent_redirect = False
    redirect_resp.headers = {"Location": "http://127.0.0.1/admin"}
    mock_session = MagicMock()
    mock_session.request.return_value = redirect_resp

    from zotero_cli.core.utils.url_safety import safe_head

    with pytest.raises(UnsafeURLError):
        safe_head("http://93.184.216.34/", session=mock_session)
    assert mock_session.request.call_args.args[0] == "HEAD"


def test_safe_get_text_caps_the_body():
    from zotero_cli.core.utils.url_safety import ResponseTooLargeError, safe_get_text

    big = MagicMock(spec=requests.Response)
    big.is_redirect = False
    big.is_permanent_redirect = False
    big.headers = {}
    big.url = "http://93.184.216.34/"
    big.iter_content.return_value = iter([b"x" * 600, b"x" * 600])
    mock_session = MagicMock()
    mock_session.request.return_value = big

    with pytest.raises(ResponseTooLargeError):
        safe_get_text("http://93.184.216.34/", max_bytes=1000, session=mock_session)


@pytest.mark.parametrize(
    "content,expected",
    [
        (b"%PDF-1.7\n...", True),
        (b"\n\r  %PDF-1.4", True),
        (b"<html>not a pdf</html>", False),
        (b"", False),
        (b"x" * 2000 + b"%PDF-1.7", False),
    ],
)
def test_looks_like_pdf(content, expected):
    from zotero_cli.core.utils.url_safety import looks_like_pdf

    assert looks_like_pdf(content) is expected
