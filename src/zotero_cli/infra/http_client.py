import logging
import secrets
import sys
import time
from typing import Any, Dict, Optional, cast

import requests
from tenacity import (
    RetryCallState,
    after_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
)

from zotero_cli.core.exceptions import (
    AuthError,
    Conflict,
    NotFound,
    Unavailable,
    ZoteroCliError,
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

# Issue #398: every request has a timeout, and retries are bounded in count
# and in total time, so a network outage fails in about a minute instead of
# hanging for five.
REQUEST_TIMEOUT = (5, 30)  # connect, read (seconds)
POST_TIMEOUT = (5, 60)
MAX_ATTEMPTS = 4
MAX_RETRY_SECONDS = 60


def is_post_retryable(exception: BaseException) -> bool:
    """With a write token, retrying a POST can't duplicate anything, so a
    read timeout (the request may have been committed) is retried too."""
    return is_http_retryable(exception) or isinstance(exception, requests.exceptions.Timeout)


def is_read_retryable(exception: BaseException) -> bool:
    return is_http_retryable(exception) or isinstance(exception, requests.exceptions.Timeout)


def is_duplicate_write(response: requests.Response) -> bool:
    """Zotero's answer to a write token it has already processed."""
    return response.status_code == 412 and "write token" in (response.text or "").lower()


def _seconds(value: Any) -> Optional[float]:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def _server_delay(exception: Optional[BaseException]) -> Optional[float]:
    """Seconds the server asked us to wait (Retry-After, or Zotero's Backoff)."""
    response = getattr(exception, "response", None)
    headers = getattr(response, "headers", None) or {}
    for name in ("Retry-After", "Backoff"):
        seconds = _seconds(headers.get(name))
        if seconds is not None:
            return seconds
    return None


_exponential = wait_exponential(multiplier=2, min=2, max=20)


def _wait(retry_state: RetryCallState) -> float:
    """Wait what the server asked for, else back off exponentially."""
    outcome = retry_state.outcome
    requested = _server_delay(outcome.exception() if outcome else None)
    if requested is not None:
        return min(requested, MAX_RETRY_SECONDS)
    return float(_exponential(retry_state))


def _notice(retry_state: RetryCallState) -> None:
    """One stderr line on the first retry, so a slow command isn't silent."""
    outcome = retry_state.outcome
    error = outcome.exception() if outcome else None
    logger.warning("Zotero API request failed (%s); retrying.", error)
    if retry_state.attempt_number == 1:
        print("Zotero API unreachable or busy, retrying...", file=sys.stderr)


def translate_error(exception: requests.RequestException, what: str) -> ZoteroCliError:
    """The CLI error for a request that failed after retries (Issue #369):
    a rejected key, a missing object and an outage used to look alike."""
    if isinstance(exception, requests.exceptions.HTTPError) and exception.response is not None:
        status = exception.response.status_code
        if status in (401, 403):
            return AuthError(
                f"Zotero rejected the request for {what} (HTTP {status}): the API key is invalid "
                "or has no access to this library. Run `zotero-cli init`, or check ZOTERO_API_KEY "
                "and the library ID."
            )
        if status == 404:
            return NotFound(f"{what} not found (HTTP 404).")
        if status == 412:
            return Conflict(f"{what} changed on the server since it was read (HTTP 412).")
        if status == 429 or status >= 500:
            return Unavailable(f"The Zotero API is unavailable (HTTP {status}) after retries.")
        return ZoteroCliError(f"The Zotero API refused the request for {what} (HTTP {status}).")
    return Unavailable(
        f"Could not reach the Zotero API ({type(exception).__name__}); check your network "
        "connection and try again."
    )


class ZoteroHttpClient:
    """
    Low-level HTTP client for the Zotero Web API: authentication headers,
    the user/group URL prefix, timeouts, bounded retries that honour the
    server's Retry-After/Backoff, and typed errors once retries run out.
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
        # Zotero's `Backoff` header asks clients to pause before the next
        # request, even after a successful one.
        self._pause_until = 0.0

    def _respect_backoff(self) -> None:
        remaining = self._pause_until - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, MAX_RETRY_SECONDS))

    def _note_backoff(self, response: requests.Response) -> None:
        backoff = _seconds(response.headers.get("Backoff"))
        if backoff is not None:
            self._pause_until = time.monotonic() + backoff

    # --- GET -----------------------------------------------------------------

    def get(
        self, endpoint: str, params: Optional[Dict] = None, use_prefix: bool = True, **kwargs: Any
    ) -> requests.Response:
        url = f"{self.api_prefix}/{endpoint}" if use_prefix else f"{self.BASE_URL}/{endpoint}"
        try:
            return self._get_with_retries(url, params, **kwargs)
        except requests.RequestException as e:
            raise translate_error(e, endpoint) from e

    @retry(
        stop=(stop_after_attempt(MAX_ATTEMPTS) | stop_after_delay(MAX_RETRY_SECONDS)),
        wait=_wait,
        retry=retry_if_exception(is_read_retryable),
        before_sleep=_notice,
        reraise=True,
    )
    def _get_with_retries(
        self, url: str, params: Optional[Dict], **kwargs: Any
    ) -> requests.Response:
        self._respect_backoff()
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        response = self.session.get(url, params=params, **kwargs)
        self._update_version(response)
        self._note_backoff(response)
        response.raise_for_status()
        return response

    # --- POST ----------------------------------------------------------------

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
        try:
            return self._post_with_retries(url, json_data, h)
        except requests.RequestException as e:
            raise translate_error(e, endpoint) from e

    @retry(
        stop=(stop_after_attempt(5) | stop_after_delay(90)),
        wait=_wait,
        retry=retry_if_exception(is_post_retryable),
        before_sleep=_notice,
        reraise=True,
    )
    def _post_with_retries(
        self, url: str, json_data: Any, headers: Dict[str, Any]
    ) -> requests.Response:
        self._respect_backoff()
        response = self.session.post(url, json=json_data, headers=headers, timeout=POST_TIMEOUT)
        self._update_version(response)
        self._note_backoff(response)
        if is_duplicate_write(response):
            logger.warning(
                "Zotero had already processed this write (an earlier attempt succeeded before "
                "the connection failed); it was not sent again."
            )
            return response
        response.raise_for_status()
        return response

    # --- PATCH / DELETE --------------------------------------------------------

    def patch(
        self, endpoint: str, json_data: Any, version_check: bool = False
    ) -> requests.Response:
        """A 412 (version precondition failed) is returned, not raised, so
        the caller can decide what to do."""
        url = f"{self.api_prefix}/{endpoint}"
        headers = dict(self.session.headers).copy()
        if version_check:
            headers["If-Unmodified-Since-Version"] = str(self.last_library_version)
        try:
            return self._write_with_retries("patch", url, headers=headers, json=json_data)
        except requests.RequestException as e:
            raise translate_error(e, endpoint) from e

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
        try:
            return self._write_with_retries("delete", url, headers=headers, params=params)
        except requests.RequestException as e:
            raise translate_error(e, endpoint) from e

    @retry(
        stop=(stop_after_attempt(MAX_ATTEMPTS) | stop_after_delay(MAX_RETRY_SECONDS)),
        wait=_wait,
        retry=retry_if_exception(is_read_retryable),
        before_sleep=_notice,
        reraise=True,
    )
    def _write_with_retries(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        # PATCH and DELETE are idempotent, so retrying them is safe.
        self._respect_backoff()
        response: requests.Response = getattr(self.session, method)(
            url, timeout=REQUEST_TIMEOUT, **kwargs
        )
        if response.status_code != 412:
            response.raise_for_status()
        self._update_version(response)
        self._note_backoff(response)
        return response

    # --- File upload / form posts ----------------------------------------------

    @retry(
        stop=(stop_after_attempt(MAX_ATTEMPTS) | stop_after_delay(MAX_RETRY_SECONDS)),
        wait=_wait,
        retry=retry_if_exception(is_http_retryable),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def upload_file(self, url: str, data: Dict, files: Dict) -> requests.Response:
        """
        Direct upload bypasses the Zotero Prefix, usually going to S3 or a specific upload URL.
        """
        response = requests.post(url, data=data, files=files, timeout=(5, 120))
        response.raise_for_status()
        return response

    @retry(
        stop=(stop_after_attempt(MAX_ATTEMPTS) | stop_after_delay(MAX_RETRY_SECONDS)),
        wait=_wait,
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

        response = self.session.post(url, data=data, headers=h, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response

    @staticmethod
    @retry(
        stop=(stop_after_attempt(MAX_ATTEMPTS) | stop_after_delay(MAX_RETRY_SECONDS)),
        wait=_wait,
        retry=retry_if_exception(is_read_retryable),
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
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    def _update_version(self, response: requests.Response) -> None:
        version = response.headers.get("Last-Modified-Version")
        if version:
            self.last_library_version = int(version)
