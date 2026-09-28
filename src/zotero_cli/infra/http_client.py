import logging
import secrets
from typing import Any, Dict, Optional, cast

import requests
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
)


def is_http_retryable(exception: BaseException) -> bool:
    """Check if an exception is a retryable HTTP error or connection error."""
    if isinstance(exception, requests.exceptions.ConnectionError):
        return True
    if isinstance(exception, requests.exceptions.HTTPError):
        status_code = exception.response.status_code
        return status_code == 429 or 500 <= status_code < 600
    return False


logger = logging.getLogger(__name__)

# Issue #409: a POST that creates objects carries a random write token, the
# same on every retry of that request, so Zotero processes it at most once.
IDEMPOTENCY_HEADER = "Zotero-Write-Token"
POST_TIMEOUT = 60


def is_post_retryable(exception: BaseException) -> bool:
    """With a write token, retrying a POST can't duplicate anything, so a
    read timeout (the request may have been committed) is retried too."""
    return is_http_retryable(exception) or isinstance(exception, requests.exceptions.Timeout)


def is_duplicate_write(response: requests.Response) -> bool:
    """Zotero's answer to a write token it has already processed."""
    return response.status_code == 412 and "write token" in (response.text or "").lower()


class ZoteroHttpClient:
    """
    Low-level HTTP Client for Zotero API.
    Responsibilities:
    - Authentication (Headers)
    - Base URL construction (User vs Group)
    - Session management
    - Rate Limiting / Retries (TODO)
    - Error Handling (Basic)
    """

    API_VERSION = "3"
    BASE_URL = "https://api.zotero.org"

    def __init__(self, api_key: str, library_id: str, library_type: str = "group"):
        self.api_key = api_key
        self.library_id = library_id
        self.library_type = library_type

        self.session = requests.Session()
        self.session.headers.update(
            {"Zotero-API-Version": self.API_VERSION, "Zotero-API-Key": self.api_key}
        )

        # Determine prefix: /groups/123 or /users/123
        prefix = "users" if library_type == "user" else "groups"
        self.api_prefix = f"{self.BASE_URL}/{prefix}/{self.library_id}"

        # State
        self.last_library_version = 0

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(is_http_retryable),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def get(
        self, endpoint: str, params: Optional[Dict] = None, use_prefix: bool = True, **kwargs: Any
    ) -> requests.Response:
        url = f"{self.api_prefix}/{endpoint}" if use_prefix else f"{self.BASE_URL}/{endpoint}"
        # Strip leading slash if present in endpoint to avoid double slash issues?
        # requests handles it mostly, but let's be clean.

        response = self.session.get(url, params=params, **kwargs)
        self._update_version(response)
        response.raise_for_status()
        return response

    def post(
        self,
        endpoint: str,
        json_data: Any,
        use_prefix: bool = True,
        headers: Optional[Dict] = None,
        version_check: bool = False,
    ) -> requests.Response:
        """POST with retries. An object-creating POST (a JSON array) gets a
        write token here, outside the retry loop, so every retry sends the
        same one (Issue #409: a retry after a dropped connection used to
        create the items again). If Zotero already processed it, the 412 is
        returned instead of raised; see `is_duplicate_write`."""
        url = f"{self.api_prefix}/{endpoint}" if use_prefix else f"{self.BASE_URL}/{endpoint}"
        h = dict(self.session.headers).copy()
        if headers:
            h.update(headers)
        if version_check:
            h["If-Unmodified-Since-Version"] = str(self.last_library_version)
        if isinstance(json_data, list) and IDEMPOTENCY_HEADER not in h:
            h[IDEMPOTENCY_HEADER] = secrets.token_hex(16)
        return self._post_with_retries(url, json_data, h)

    @retry(
        stop=(stop_after_attempt(5) | stop_after_delay(90)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception(is_post_retryable),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _post_with_retries(
        self, url: str, json_data: Any, headers: Dict[str, Any]
    ) -> requests.Response:
        response = self.session.post(url, json=json_data, headers=headers, timeout=POST_TIMEOUT)
        self._update_version(response)
        if is_duplicate_write(response):
            logger.warning(
                "Zotero had already processed this write (an earlier attempt succeeded before "
                "the connection failed); it was not sent again."
            )
            return response
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(is_http_retryable),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def patch(
        self, endpoint: str, json_data: Any, version_check: bool = False
    ) -> requests.Response:
        url = f"{self.api_prefix}/{endpoint}"
        headers = dict(self.session.headers).copy()

        # Concurrency Control
        if version_check:
            headers["If-Unmodified-Since-Version"] = str(self.last_library_version)

        response = self.session.patch(url, json=json_data, headers=headers)

        # Simple retry logic for 412 could go here, but logic currently resides in caller.
        # For now, we return raw response for caller to handle 412.

        if response.status_code != 412:
            response.raise_for_status()

        self._update_version(response)
        return response

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(is_http_retryable),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def delete(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        version_check: bool = True,
        version: Optional[int] = None,
    ) -> requests.Response:
        """DELETE with optimistic concurrency. `version` is the object's own
        version (single-object deletes, per the Zotero API); without it the
        last-seen library version is sent. A 412 is returned, not raised."""
        url = f"{self.api_prefix}/{endpoint}"
        headers = dict(self.session.headers).copy()
        if version is not None:
            headers["If-Unmodified-Since-Version"] = str(version)
        elif version_check:
            headers["If-Unmodified-Since-Version"] = str(self.last_library_version)

        response = self.session.delete(url, params=params, headers=headers)
        if response.status_code != 412:
            response.raise_for_status()

        self._update_version(response)
        return response

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(is_http_retryable),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def upload_file(self, url: str, data: Dict, files: Dict) -> requests.Response:
        """
        Direct upload bypasses the Zotero Prefix, usually going to S3 or a specific upload URL.
        """
        response = requests.post(url, data=data, files=files, timeout=30)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(is_http_retryable),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def post_form(
        self, endpoint: str, data: Dict, headers: Optional[Dict] = None
    ) -> requests.Response:
        """
        For multipart/form-data or urlencoded posts (like attachment authorization).
        """
        url = f"{self.api_prefix}/{endpoint}"
        h = dict(self.session.headers).copy()
        if headers:
            h.update(headers)

        response = self.session.post(url, data=data, headers=h)
        response.raise_for_status()
        return response

    @staticmethod
    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(is_http_retryable),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def resolve_key_identity(api_key: str) -> Dict[str, Any]:
        """
        Calls GET /keys/current - library-independent by design, since
        resolving a personal library's userID from a bare key is exactly
        what a caller with no library_id yet needs it for (Issue #178).
        The key goes only in the header: `/keys/<api_key>` would put it in
        the URL, which ends up in exception messages and logs.
        Raises requests.HTTPError (e.g. 403 for an invalid/revoked key) or
        a connection error on failure; callers decide how to present that.
        """
        url = f"{ZoteroHttpClient.BASE_URL}/keys/current"
        response = requests.get(
            url,
            headers={
                "Zotero-API-Version": ZoteroHttpClient.API_VERSION,
                "Zotero-API-Key": api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    def _update_version(self, response: requests.Response) -> None:
        version = response.headers.get("Last-Modified-Version")
        if version:
            self.last_library_version = int(version)
