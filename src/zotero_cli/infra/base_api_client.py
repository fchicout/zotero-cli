import logging
import time
from abc import ABC
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from zotero_cli.core.utils.user_agent import user_agent

# Configure logging
logger = logging.getLogger(__name__)

__all__ = ["BaseAPIClient", "user_agent"]

# Rate-limit policy (Issue #420): a 429 is retried at most this many times,
# waiting what the provider's Retry-After asks, and never more than this long
# in one go. A provider that wants a longer wait (a daily quota that resets
# at midnight UTC) can't be waited out inside a command, so the request
# fails at once with a warning that says so instead of hanging.
MAX_RATE_LIMIT_RETRIES = 2
MAX_RATE_LIMIT_WAIT = 30.0
_DEFAULT_RATE_LIMIT_WAIT = 5.0


def retry_after_seconds(response: requests.Response) -> Optional[float]:
    """Seconds a `Retry-After` header asks for (delta-seconds or HTTP-date),
    or None when it's absent or unreadable."""
    value = response.headers.get("Retry-After") if response.headers else None
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


class BaseAPIClient(ABC):
    """
    Abstract base class for Metadata Providers.
    Encapsulates HTTP transport, retries, and error handling.
    """

    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        min_request_interval: float = 0.34,
        contact_email: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(headers or {})
        if "User-Agent" not in self.session.headers:
            self.session.headers["User-Agent"] = user_agent(contact_email)

        # Proactive pacing (Issue #268): reactive retry/backoff (below)
        # only kicks in *after* a request is already rejected - it does
        # nothing to stop a burst of calls from tripping a provider's rate
        # limit in the first place. Most metadata-provider clients had no
        # pacing at all; ~3 req/s is a conservative default "polite pool"
        # rate shared by several of these APIs' own documented limits.
        # Subclasses that already self-throttle more precisely (e.g. with
        # an API-key-aware rate, like pubmed_api.py/semantic_scholar_api.py)
        # pass min_request_interval=0 to opt out of this redundant layer.
        self.min_request_interval = min_request_interval
        self._last_request_time = 0.0

    def _apply_rate_limit(self) -> None:
        if self.min_request_interval <= 0:
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
            )
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _get(
        self,
        endpoint: str = "",
        params: Optional[Dict[str, Any]] = None,
        url_override: Optional[str] = None,
    ) -> requests.Response:
        """
        Execute a GET request with built-in retry logic.

        Args:
            endpoint: The API endpoint (e.g., "works/10.1234/5678").
            params: Query parameters.
            url_override: If provided, ignores self.base_url and uses this full URL.

        Returns:
            requests.Response object.

        Raises:
            requests.exceptions.HTTPError: If the status code is 4xx/5xx (except 404 which might be handled by caller).
        """
        if url_override:
            url = url_override
        else:
            url = f"{self.base_url}/{endpoint.lstrip('/')}" if endpoint else self.base_url

        provider = type(self).__name__
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            self._apply_rate_limit()
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 429:
                break
            requested = retry_after_seconds(response)
            wait = _DEFAULT_RATE_LIMIT_WAIT * (attempt + 1) if requested is None else requested
            if wait > MAX_RATE_LIMIT_WAIT or attempt == MAX_RATE_LIMIT_RETRIES:
                logger.warning(
                    "%s: rate limited (HTTP 429), not retrying%s. Its limit or daily quota is "
                    "used up; try again later or configure an API key for this provider.",
                    provider,
                    f" (Retry-After {requested:.0f}s)" if requested is not None else "",
                )
                break
            logger.warning(
                "%s: rate limited (HTTP 429); waiting %.0fs (retry %d/%d).",
                provider,
                wait,
                attempt + 1,
                MAX_RATE_LIMIT_RETRIES,
            )
            time.sleep(wait)
        response.raise_for_status()
        return response
