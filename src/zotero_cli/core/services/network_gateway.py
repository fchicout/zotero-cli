import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from zotero_cli.core.exceptions import RetryableError
from zotero_cli.core.utils.url_safety import (
    MAX_REDIRECTS,
    UnsafeURLError,
    pin_public_ips,
    read_capped_async,
    validate_public_url,
)
from zotero_cli.core.utils.user_agent import user_agent

logger = logging.getLogger(__name__)

# Issue #241: headers that must not survive a cross-origin redirect hop.
# httpx's own built-in redirect handling only strips "Authorization" this
# way - we manage redirects manually (Issue #235), so we're responsible
# for the same protection, extended to non-standard auth headers this
# codebase actually uses (e.g. Semantic Scholar's x-api-key).
_SENSITIVE_HEADERS = {"authorization", "x-api-key"}


def _origin(url: str) -> tuple:
    parsed = urlparse(url)
    default_port = 443 if parsed.scheme == "https" else 80
    return (parsed.scheme, parsed.hostname, parsed.port or default_port)


class NetworkGateway:
    """
    Gateway for external HTTP requests with resilience and rate limit
    handling. Every request identifies itself as zotero-cli (Issue #407):
    it used to send rotating browser User-Agents and, on a 403, resend the
    same request (API key included) under another identity - the kind of
    circumvention provider terms (e.g. Semantic Scholar's) forbid.
    """

    def __init__(self, agent: Optional[str] = None):
        self.user_agent = agent or user_agent()
        # follow_redirects=False deliberately: redirects are followed
        # manually in _fetch_validated, re-validating each hop against
        # validate_public_url (Issue #235) - trusting the client's
        # built-in redirect handling would let a validated public URL
        # redirect straight into a loopback/private/link-local address.
        # pin_public_ips: connect only to the address validate_public_url
        # approved, not whatever a second DNS lookup returns.
        self._client = pin_public_ips(httpx.AsyncClient(timeout=30.0, follow_redirects=False))

    async def close(self) -> None:
        await self._client.aclose()

    async def _fetch_validated(
        self, method: str, url: str, headers: Dict[str, str], **kwargs: Any
    ) -> httpx.Response:
        """SSRF guard (Issue #235): validates the URL, and every redirect
        hop, before it's fetched - every external URL this gateway sees
        may originate from Zotero item data or a third-party API
        response, neither of which is trustworthy."""
        current_url = url
        current_headers = dict(headers)
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_url(current_url)
            request = self._client.build_request(
                method, current_url, headers=current_headers, **kwargs
            )
            response = await self._client.send(request, stream=True)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    return await read_capped_async(response)
                await response.aclose()
                previous_url = current_url
                current_url = str(httpx.URL(current_url).join(location))
                if _origin(previous_url) != _origin(current_url):
                    current_headers = {
                        k: v
                        for k, v in current_headers.items()
                        if k.lower() not in _SENSITIVE_HEADERS
                    }
                continue
            # Issue #239: enforce a hard response-size cap here, streamed
            # rather than trusting the client to buffer an unbounded body
            # into memory - every URL this gateway fetches may originate
            # from Zotero item data or a third-party API response.
            return await read_capped_async(response)
        raise UnsafeURLError(f"Too many redirects while fetching {url!r}")

    async def get(
        self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs: Any
    ) -> httpx.Response:
        """
        Performs a GET request with automatic retries on connection errors.
        """
        return await self._execute_request("GET", url, headers, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _execute_request(
        self, method: str, url: str, headers: Optional[Dict[str, str]] = None, **kwargs: Any
    ) -> httpx.Response:
        request_headers = dict(headers or {})
        if not any(k.lower() == "user-agent" for k in request_headers):
            request_headers["User-Agent"] = self.user_agent

        try:
            response = await self._fetch_validated(method, url, request_headers, **kwargs)

            # Policy: 200 -> Return
            if response.status_code == 200:
                return response

            # Policy: 429/503 -> Pause -> RetryableError
            if response.status_code in (429, 503):
                retry_after = 60
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                raise RetryableError(
                    f"Rate limited ({response.status_code})", retry_after=retry_after
                )

            # Policy: 403 -> fail, never retry under another identity.
            if response.status_code == 403:
                # With an API key/auth header (anything beyond User-Agent),
                # a 403 almost always means that credential is invalid,
                # expired or lacks access (Issue #223, seen with a
                # configured semantic_scholar_api_key getting 403 while the
                # unauthenticated request succeeds). Say so clearly instead
                # of a generic HTTPStatusError.
                auth_headers = [h for h in request_headers if h.lower() != "user-agent"]
                if auth_headers:
                    msg = (
                        f"403 Forbidden at {url} with a configured credential present "
                        f"({', '.join(auth_headers)}). This almost always means that API "
                        "key is invalid, expired, or lacks access - not a rate limit. "
                        "Verify the key, or remove it to fall back to unauthenticated access."
                    )
                    logger.error(msg)
                    raise ValueError(msg)
                logger.error(f"403 Forbidden at {url}.")
                response.raise_for_status()

            # Raise for other error codes (4xx, 5xx) that are not handled above
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            # Re-raise RetryableError if it was wrapped or caught?
            # No, we raised RetryableError manually.
            # HTTPStatusError comes from raise_for_status().
            if e.response.status_code in (429, 503):
                # Should be caught by the manual check, but just in case
                raise RetryableError(f"HTTP Error {e.response.status_code}") from e
            raise e
