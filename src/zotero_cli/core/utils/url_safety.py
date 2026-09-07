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
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
import requests

MAX_REDIRECTS = 5
_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(ValueError):
    """Raised when a URL is disallowed (bad scheme, or resolves to a
    non-public address) rather than fetched."""


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
    client: httpx.AsyncClient, url: str, headers: Optional[dict] = None, **kwargs: Any
) -> httpx.Response:
    """
    Async (httpx-based) equivalent of `client.get`, but validating the
    URL - and every redirect hop - against validate_public_url before
    it's fetched. Used both by NetworkGateway and any resolver that
    manages its own httpx.AsyncClient.
    """
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_url(current_url)
        response = await client.get(current_url, headers=headers, follow_redirects=False, **kwargs)
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                return response
            current_url = str(httpx.URL(current_url).join(location))
            continue
        return response
    raise UnsafeURLError(f"Too many redirects while fetching {url!r}")
