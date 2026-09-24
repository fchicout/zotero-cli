"""
Shared SSRF guard for every code path that fetches a URL sourced from
Zotero item data or a third-party API response (Issue #235) - PDF
resolvers, attachment auto-download, thesis-import PDF fetch. None of
these URLs are trustworthy: any collaborator with write access to a
shared library can set `item.url`, and third-party bibliographic APIs
are themselves untrusted input.

`requests`/`httpx` follow redirects by default, so validating only the
initial URL is not enough - a validated public URL can still redirect to
a private/loopback address. Every fetch here re-validates before each
hop instead of trusting the HTTP client's built-in redirect handling.

Validating a hostname and then letting the HTTP client resolve it again
leaves a gap: a DNS answer with a zero TTL can return a public address
for the check and 127.0.0.1 for the connection. `safe_get`/`safe_head`
and `pin_public_ips` close it by connecting to the exact address that was
validated, while TLS still verifies the certificate against the hostname.
"""

import ipaddress
import socket
from typing import Any, Iterator, List, Optional, Union
from urllib.parse import urlparse

import httpcore
import httpx
import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

MAX_REDIRECTS = 5
_ALLOWED_SCHEMES = {"http", "https"}

# Issue #239: neither requests nor httpx caps response body size by
# default - a malicious/compromised source (or, combined with #235's SSRF
# finding, an attacker-controlled item.url) can serve an arbitrarily
# large or slow-drip body and exhaust memory/disk on the machine running
# `item pdf fetch`/`item attach-pdfs`. 50MB comfortably covers a
# legitimate PDF while capping the damage of a hostile one.
MAX_RESPONSE_BYTES = 50 * 1024 * 1024


class UnsafeURLError(ValueError):
    """Raised when a URL is disallowed (bad scheme, or resolves to a
    non-public address) rather than fetched."""


class ResponseTooLargeError(ValueError):
    """Raised when a fetched response body exceeds MAX_RESPONSE_BYTES,
    whether announced upfront via Content-Length or discovered while
    streaming (a hostile server can lie about or omit Content-Length)."""


def _check_content_length(headers: Any, max_bytes: int, url: str) -> None:
    """Best-effort upfront rejection when a server honestly declares an
    oversized body - does not replace the streaming cutoff below, since
    Content-Length can be absent, wrong, or lied about."""
    content_length = headers.get("content-length") or headers.get("Content-Length")
    if content_length is None:
        return
    try:
        declared = int(content_length)
    except (TypeError, ValueError):
        return
    if declared > max_bytes:
        raise ResponseTooLargeError(
            f"Response for {url!r} declared Content-Length {declared} bytes, "
            f"exceeding the {max_bytes}-byte cap - refusing to download"
        )


def iter_capped_content(
    response: requests.Response,
    chunk_size: int = 8192,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> Iterator[bytes]:
    """Wraps `response.iter_content()` (a `requests.Response` obtained via
    `safe_get(..., stream=True)`) enforcing max_bytes - both an upfront
    Content-Length check and a hard cutoff while streaming, so a hostile
    server can't exhaust memory/disk by lying about or omitting
    Content-Length (Issue #239)."""
    url = str(getattr(response, "url", ""))
    _check_content_length(response.headers, max_bytes, url)
    total = 0
    for chunk in response.iter_content(chunk_size=chunk_size):
        total += len(chunk)
        if total > max_bytes:
            raise ResponseTooLargeError(
                f"Response for {url!r} exceeded the {max_bytes}-byte cap "
                "while streaming - refusing to continue"
            )
        yield chunk


async def read_capped_async(
    response: httpx.Response, max_bytes: int = MAX_RESPONSE_BYTES
) -> httpx.Response:
    """Reads a streamed (`stream=True`) httpx.Response into memory,
    enforcing max_bytes via an upfront Content-Length check plus a hard
    cutoff while streaming (Issue #239). Returns a fully-read
    httpx.Response with the same status/headers, so callers can use
    `.content`/`.text`/`.json()` exactly as before."""
    url = str(response.url)
    try:
        _check_content_length(response.headers, max_bytes, url)
        chunks = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLargeError(
                    f"Response for {url!r} exceeded the {max_bytes}-byte cap "
                    "while streaming - refusing to continue"
                )
            chunks.append(chunk)
    finally:
        await response.aclose()
    # aiter_bytes() already undid any Content-Encoding, so the joined body is
    # plain bytes. Keeping the original Content-Encoding header would make
    # httpx decode it a second time and fail with "incorrect header check"
    # on any gzip response (Issue #321); the original Content-Length is the
    # compressed size, so drop it too and let httpx recompute it.
    headers = httpx.Headers(response.headers)
    for stale in ("content-encoding", "content-length"):
        if stale in headers:
            del headers[stale]
    return httpx.Response(
        status_code=response.status_code,
        headers=headers,
        content=b"".join(chunks),
        request=response.request,
    )


IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

# Ranges Python's `is_global` still reports as global. (NOSONAR: these
# literals are a blocklist, not addresses anything connects to.)
_EXTRA_BLOCKED_NETWORKS = (
    ipaddress.ip_network("192.88.99.0/24"),  # NOSONAR - 6to4 relay anycast (deprecated)
    ipaddress.ip_network("fec0::/10"),  # NOSONAR - IPv6 site-local (deprecated)
)


def is_public_ip(ip: IPAddress) -> bool:
    """True only for globally routable unicast addresses. `is_global`
    rejects everything the old private/loopback/link-local/reserved list
    did, plus ranges it missed: 100.64.0.0/10 (CGNAT, Tailscale, some
    cloud metadata services), 192.88.99.0/24, fec0::/10 and so on. An
    IPv4-mapped IPv6 address is judged by its IPv4 address."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if any(ip in network for network in _EXTRA_BLOCKED_NETWORKS):
        return False
    return ip.is_global and not ip.is_multicast


def resolve_public_ips(hostname: str) -> List[str]:
    """Resolves `hostname` and returns its addresses, raising
    UnsafeURLError if it doesn't resolve or if ANY address isn't public."""
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Could not resolve hostname {hostname!r}: {e}") from e

    addresses: List[str] = []
    for _, _, _, _, sockaddr in addr_infos:
        address = str(sockaddr[0])
        if not is_public_ip(ipaddress.ip_address(address)):
            raise UnsafeURLError(
                f"Host {hostname!r} resolves to a non-public address ({address}) - refusing to fetch"
            )
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise UnsafeURLError(f"Could not resolve hostname {hostname!r}")
    return addresses


def validate_public_url(url: str) -> None:
    """
    Raises UnsafeURLError unless `url` is http(s) and every address its
    hostname resolves to is a public, globally routable address.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Disallowed URL scheme {parsed.scheme!r} in {url!r}")
    if not parsed.hostname:
        raise UnsafeURLError(f"URL has no hostname: {url!r}")
    try:
        resolve_public_ips(parsed.hostname)
    except UnsafeURLError as e:
        raise UnsafeURLError(f"{e} (URL {url!r})") from e


def looks_like_pdf(content: bytes) -> bool:
    """True if `content` carries the PDF header. The spec allows it anywhere
    in the first 1024 bytes; a `Content-Type: application/pdf` header alone
    proves nothing about the body."""
    return b"%PDF-" in content[:1024]


# --- Connection pinning -------------------------------------------------
#
# The connection classes below resolve and validate the host themselves,
# at connect time, and connect to the validated address. urllib3 opens the
# socket from `_dns_host`, which also backs its `host` property - used for
# the TLS SNI name and certificate check once the socket is open - so the
# validated address is swapped in only for the socket call and the
# hostname restored straight after. httpcore passes the hostname to
# `connect_tcp` and the SNI name to `start_tls` separately. Proxied
# requests use the proxy's own connection classes, so an HTTP(S)_PROXY
# setting keeps working.


def _pinned_new_conn(conn: HTTPConnection) -> socket.socket:
    hostname = conn._dns_host
    conn._dns_host = resolve_public_ips(hostname)[0]
    try:
        # HTTPSConnection inherits _new_conn from HTTPConnection unchanged.
        return HTTPConnection._new_conn(conn)
    finally:
        conn._dns_host = hostname


class _PinnedHTTPConnection(HTTPConnection):
    _new_conn = _pinned_new_conn


class _PinnedHTTPSConnection(HTTPSConnection):
    _new_conn = _pinned_new_conn


class _PinnedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _PinnedHTTPConnection


class _PinnedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection


class PublicOnlyAdapter(HTTPAdapter):
    """requests adapter whose direct connections only go to validated
    public addresses."""

    def init_poolmanager(
        self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any
    ) -> None:
        super().init_poolmanager(connections, maxsize, block, **pool_kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            "http": _PinnedHTTPConnectionPool,
            "https": _PinnedHTTPSConnectionPool,
        }


def public_only_session(session: Optional[requests.Session] = None) -> requests.Session:
    """Mounts PublicOnlyAdapter on `session` (a new one by default)."""
    session = session or requests.Session()
    adapter = PublicOnlyAdapter()
    # NOSONAR: mounting on http:// is what extends the SSRF guard to
    # plain-HTTP URLs; it doesn't make any request use HTTP.
    session.mount("http://", adapter)  # NOSONAR
    session.mount("https://", adapter)
    return session


class _PublicOnlyAsyncBackend(httpcore.AsyncNetworkBackend):
    # connect_unix_socket is deliberately not overridden: the base class
    # refuses it (NotImplementedError), and these clients never set `uds`.

    def __init__(self, inner: httpcore.AsyncNetworkBackend):
        self._inner = inner

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        address = resolve_public_ips(host)[0]
        return await self._inner.connect_tcp(
            address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def pin_public_ips(client: httpx.AsyncClient) -> httpx.AsyncClient:
    """Makes `client`'s direct (non-proxied) connections go only to
    validated public addresses. Patches the default transport's connection
    pool in place, so env-configured proxy mounts stay as they are."""
    transport = getattr(client, "_transport", None)
    if not isinstance(transport, httpx.AsyncHTTPTransport):
        return client  # a test double; test_url_safety pins a real client
    pool = getattr(transport, "_pool", None)
    if not isinstance(pool, httpcore.AsyncConnectionPool):
        # Internals not as expected (e.g. a changed httpx release): fail
        # loudly rather than leave the client unpinned.
        raise TypeError("pin_public_ips needs a client using httpx's default transport")
    pool._network_backend = _PublicOnlyAsyncBackend(pool._network_backend)
    return client


def _safe_request(method: str, url: str, **kwargs: Any) -> requests.Response:
    session = public_only_session(kwargs.pop("session", None))
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_url(current_url)
        response = session.request(method, current_url, allow_redirects=False, **kwargs)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            if not location:
                return response
            response.close()
            current_url = str(httpx.URL(current_url).join(location))
            continue
        return response
    raise UnsafeURLError(f"Too many redirects while fetching {url!r}")


def safe_get(url: str, **kwargs: Any) -> requests.Response:
    """
    Synchronous (requests-based) equivalent of `requests.get`, but
    validating the URL - and every redirect hop - against
    validate_public_url, and connecting only to the validated address.
    """
    return _safe_request("GET", url, **kwargs)


def safe_head(url: str, **kwargs: Any) -> requests.Response:
    """`safe_get`'s HEAD counterpart, for probing a link without
    downloading it."""
    return _safe_request("HEAD", url, **kwargs)


def safe_get_text(url: str, max_bytes: int = 5 * 1024 * 1024, **kwargs: Any) -> requests.Response:
    """`safe_get` for an HTML page: reads at most `max_bytes` of the body
    (streaming, so a huge or endless page can't exhaust memory) and returns
    the response with that body loaded, so `.text` works as usual."""
    response = safe_get(url, stream=True, **kwargs)
    try:
        response._content = b"".join(iter_capped_content(response, max_bytes=max_bytes))
    finally:
        response.close()
    return response


async def safe_async_get(
    client: httpx.AsyncClient,
    url: str,
    headers: Optional[dict] = None,
    max_bytes: int = MAX_RESPONSE_BYTES,
    **kwargs: Any,
) -> httpx.Response:
    """
    Async (httpx-based) equivalent of `client.get`, but validating the
    URL - and every redirect hop - against validate_public_url before
    it's fetched, and enforcing max_bytes on the response body (Issue
    #239) via streaming rather than trusting the client to buffer an
    unbounded body into memory. Used both by NetworkGateway and any
    resolver that manages its own httpx.AsyncClient; pass a client set up
    with `pin_public_ips` so connections go only to validated addresses.
    """
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_url(current_url)
        request = client.build_request("GET", current_url, headers=headers, **kwargs)
        response = await client.send(request, stream=True)
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                return await read_capped_async(response, max_bytes)
            await response.aclose()
            current_url = str(httpx.URL(current_url).join(location))
            continue
        return await read_capped_async(response, max_bytes)
    raise UnsafeURLError(f"Too many redirects while fetching {url!r}")
