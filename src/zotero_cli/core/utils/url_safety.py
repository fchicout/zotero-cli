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
"""

import ipaddress
import socket
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

import httpx
import requests

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
    return httpx.Response(
        status_code=response.status_code,
        headers=response.headers,
        content=b"".join(chunks),
        request=response.request,
    )


def validate_public_url(url: str) -> None:
    """
    Raises UnsafeURLError unless `url` is http(s) and every address its
    hostname resolves to is a public, routable address - not
    loopback/private/link-local/multicast/reserved/unspecified.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Disallowed URL scheme {parsed.scheme!r} in {url!r}")
    if not parsed.hostname:
        raise UnsafeURLError(f"URL has no hostname: {url!r}")

    try:
        addr_infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Could not resolve hostname {parsed.hostname!r}: {e}") from e

    for family, _, _, _, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeURLError(
                f"URL {url!r} resolves to a non-public address ({ip}) - refusing to fetch"
            )


def safe_get(url: str, **kwargs: Any) -> requests.Response:
    """
    Synchronous (requests-based) equivalent of `requests.get`, but
    validating the URL - and every redirect hop - against
    validate_public_url before it's fetched.
    """
    session = kwargs.pop("session", None) or requests.Session()
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_url(current_url)
        response = session.get(current_url, allow_redirects=False, **kwargs)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            if not location:
                return response
            current_url = str(httpx.URL(current_url).join(location))
            continue
        return response
    raise UnsafeURLError(f"Too many redirects while fetching {url!r}")


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
    resolver that manages its own httpx.AsyncClient.
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
