"""
Issue #268: reactive retry/backoff alone doesn't stop a burst of requests
from tripping a provider's rate limit in the first place. BaseAPIClient
now self-throttles proactively before every request; these tests exercise
that pacing directly rather than through a specific metadata-provider
subclass.
"""

from unittest.mock import MagicMock, patch

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
