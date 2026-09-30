"""
Issue #268: reactive retry/backoff alone doesn't stop a burst of requests
from tripping a provider's rate limit in the first place. BaseAPIClient
now self-throttles proactively before every request; these tests exercise
that pacing directly rather than through a specific metadata-provider
subclass.
"""

from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.infra.base_api_client import BaseAPIClient


class _DummyClient(BaseAPIClient):
    """BaseAPIClient is ABC-shaped only by convention (no abstractmethods
    of its own), so a minimal concrete subclass is enough to test `_get`."""


def test_apply_rate_limit_sleeps_on_back_to_back_calls():
    client = _DummyClient(base_url="https://example.test", min_request_interval=0.34)

    with patch("zotero_cli.infra.base_api_client.time") as mock_time:
        # Each _apply_rate_limit() call reads time.time() twice: once for
        # the elapsed check, once to record _last_request_time.
        mock_time.time.side_effect = [100.0, 100.0, 100.1, 100.1]
        client._apply_rate_limit()  # First call: no prior request, no sleep.
        client._apply_rate_limit()  # Second call: 0.1s elapsed < 0.34s interval.

        mock_time.sleep.assert_called_once()
        slept_for = mock_time.sleep.call_args[0][0]
        assert 0.2 < slept_for < 0.25


def test_apply_rate_limit_does_not_sleep_when_interval_already_elapsed():
    client = _DummyClient(base_url="https://example.test", min_request_interval=0.34)

    with patch("zotero_cli.infra.base_api_client.time") as mock_time:
        mock_time.time.side_effect = [100.0, 100.0, 101.0, 101.0]
        client._apply_rate_limit()
        client._apply_rate_limit()

        mock_time.sleep.assert_not_called()


def test_apply_rate_limit_disabled_when_min_interval_is_zero():
    """Subclasses that already self-throttle more precisely (pubmed_api.py,
    semantic_scholar_api.py) opt out via min_request_interval=0."""
    client = _DummyClient(base_url="https://example.test", min_request_interval=0)

    with patch("zotero_cli.infra.base_api_client.time") as mock_time:
        client._apply_rate_limit()
        client._apply_rate_limit()

        mock_time.sleep.assert_not_called()


def test_get_applies_rate_limit_before_request():
    client = _DummyClient(base_url="https://example.test")

    with (
        patch.object(client.session, "get", return_value=MagicMock(status_code=200)),
        patch.object(client, "_apply_rate_limit") as mock_throttle,
    ):
        client._get(endpoint="works/123")

    mock_throttle.assert_called_once()


def test_default_user_agent_has_no_builtin_email_and_the_real_version():
    """Issue #337: every user's traffic carried the maintainer's address."""
    from zotero_cli import __version__
    from zotero_cli.infra.base_api_client import user_agent

    anonymous = user_agent()
    assert "mailto" not in anonymous and "@" not in anonymous
    assert f"zotero-cli/{__version__}" in anonymous
    assert user_agent("me@example.org").endswith("; mailto:me@example.org)")


# --- Issue #420: a shared, bounded 429 / Retry-After policy ---------------------


def _response(status, retry_after=None):
    import requests

    response = requests.Response()
    response.status_code = status
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    response.url = "https://example.test/x"
    return response


def _client(*responses):
    client = _DummyClient(base_url="https://example.test", min_request_interval=0)
    client.session = MagicMock()
    client.session.get.side_effect = list(responses)
    return client


def test_429_waits_the_requested_time_then_retries(caplog):
    client = _client(_response(429, 3), _response(200))

    with patch("zotero_cli.infra.base_api_client.time.sleep") as sleep, caplog.at_level("WARNING"):
        assert client._get("x").status_code == 200

    sleep.assert_called_once_with(3.0)
    assert client.session.get.call_count == 2
    assert "_DummyClient" in caplog.text
    assert "rate limited" in caplog.text


def test_429_without_retry_after_backs_off_and_is_bounded():
    import requests

    from zotero_cli.infra.base_api_client import MAX_RATE_LIMIT_RETRIES

    client = _client(*[_response(429)] * (MAX_RATE_LIMIT_RETRIES + 1))

    with patch("zotero_cli.infra.base_api_client.time.sleep") as sleep:
        with pytest.raises(requests.exceptions.HTTPError):
            client._get("x")

    assert client.session.get.call_count == MAX_RATE_LIMIT_RETRIES + 1
    assert sleep.call_count == MAX_RATE_LIMIT_RETRIES


def test_429_asking_for_a_long_wait_fails_at_once(caplog):
    """A daily quota that resets at midnight can't be waited out in a command."""
    import requests

    client = _client(_response(429, 3600))

    with patch("zotero_cli.infra.base_api_client.time.sleep") as sleep, caplog.at_level("WARNING"):
        with pytest.raises(requests.exceptions.HTTPError):
            client._get("x")

    sleep.assert_not_called()
    assert client.session.get.call_count == 1
    assert "Retry-After 3600s" in caplog.text


def test_retry_after_accepts_an_http_date():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    from zotero_cli.infra.base_api_client import retry_after_seconds

    when = datetime.now(timezone.utc) + timedelta(seconds=20)
    response = _response(429, format_datetime(when, usegmt=True))
    seconds = retry_after_seconds(response)
    assert seconds is not None
    assert 15 <= seconds <= 21
    assert retry_after_seconds(_response(429, "garbage")) is None
    assert retry_after_seconds(_response(429)) is None


def test_other_errors_are_not_treated_as_rate_limits():
    import requests

    client = _client(_response(500))
    with patch("zotero_cli.infra.base_api_client.time.sleep") as sleep:
        with pytest.raises(requests.exceptions.HTTPError):
            client._get("x")
    sleep.assert_not_called()
    assert client.session.get.call_count == 1
