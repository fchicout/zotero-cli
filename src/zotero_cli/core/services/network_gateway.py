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

logger = logging.getLogger(__name__)


class NetworkGateway:
    """
    Gateway for external HTTP requests with resilience, identity rotation,
    and rate limit handling.
    """

    def __init__(self, identity_manager: IdentityManager):
        self.identity_manager = identity_manager
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def close(self):
        await self._client.aclose()

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
            response = await self._client.request(method, url, headers=request_headers, **kwargs)

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
                response = await self._client.request(
                    method, url, headers=request_headers, **kwargs
                )

                if response.status_code == 403:
                    # Fail after retry
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
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            # Let tenacity handle these
            raise e
        except Exception as e:
            # Propagate other errors
            raise e
