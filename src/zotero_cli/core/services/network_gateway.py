import logging
from typing import Any, Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from zotero_cli.core.exceptions import RetryableError
from zotero_cli.core.services.identity_manager import IdentityManager
from zotero_cli.core.utils.url_safety import (
    MAX_REDIRECTS,
    UnsafeURLError,
    read_capped_async,
    validate_public_url,
)

logger = logging.getLogger(__name__)


class NetworkGateway:
    """
    Gateway for external HTTP requests with resilience, identity rotation,
    and rate limit handling.
    """

    def __init__(self, identity_manager: IdentityManager):
        self.identity_manager = identity_manager
        # follow_redirects=False deliberately: redirects are followed
        # manually in _fetch_validated, re-validating each hop against
        # validate_public_url (Issue #235) - trusting the client's
        # built-in redirect handling would let a validated public URL
        # redirect straight into a loopback/private/link-local address.
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=False)

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
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_url(current_url)
            request = self._client.build_request(method, current_url, headers=headers, **kwargs)
            response = await self._client.send(request, stream=True)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    return await read_capped_async(response)
                await response.aclose()
                current_url = str(httpx.URL(current_url).join(location))
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
        Performs a GET request with automatic retries and identity management.
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
        # Merge headers with current identity
        request_headers = headers or {}
        if "User-Agent" not in request_headers:
            request_headers["User-Agent"] = self.identity_manager.get_current_identity()

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

            # Policy: 403 -> Rotate Identity -> Retry Once
            if response.status_code == 403:
                logger.warning(f"403 Forbidden at {url}. Rotating identity and retrying.")
                new_ua = self.identity_manager.rotate_identity()
                request_headers["User-Agent"] = new_ua

                # Retry once
                response = await self._fetch_validated(method, url, request_headers, **kwargs)

                if response.status_code == 403:
                    # Fail after retry. If an API key/auth header was sent
                    # (anything beyond User-Agent), a 403 that survives
                    # identity rotation almost certainly means that
                    # credential itself is invalid/expired/rejected, not a
                    # generic bot-block - identity rotation can't fix a bad
                    # key, so retrying it is pointless (Issue #223, seen
                    # concretely with a configured semantic_scholar_api_key
                    # getting 403 while the identical unauthenticated
                    # request succeeds). Surface that distinction clearly
                    # instead of a generic HTTPStatusError.
                    auth_headers = [
                        h for h in request_headers if h.lower() != "user-agent"
                    ]
                    if auth_headers:
                        msg = (
                            f"403 Forbidden at {url} even after identity rotation, "
                            f"with a configured credential present ({', '.join(auth_headers)}). "
                            "This almost always means that API key is invalid, expired, "
                            "or lacks access - not a rate limit or bot-block. Verify the "
                            "key, or remove it to fall back to unauthenticated access."
                        )
                        logger.error(msg)
                        raise ValueError(msg)
                    logger.error(f"403 Forbidden persists after rotation at {url}.")
                    response.raise_for_status()

                if response.status_code in (429, 503):
                    raise RetryableError(f"Rate limited after rotation ({response.status_code})")

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
