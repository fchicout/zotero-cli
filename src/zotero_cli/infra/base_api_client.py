import logging
import time
from abc import ABC
from typing import Any, Dict, Optional

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Configure logging
logger = logging.getLogger(__name__)


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
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(headers or {})
        # Default user agent if not provided
        if "User-Agent" not in self.session.headers:
            self.session.headers["User-Agent"] = "zotero-cli/1.2.0 (mailto:fchicout@gmail.com)"

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

        self._apply_rate_limit()
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response
