"""One reading of `Retry-After` (Issue #711, from #611)."""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import Mock

import pytest
import requests

from zotero_cli.core.utils.retry_after import parse_retry_after
from zotero_cli.infra.base_api_client import retry_after_seconds


@pytest.mark.parametrize(
    ("value", "expected"),
    [("30", 30.0), ("2.5", 2.5), ("0", 0.0), (7, 7.0), (" 12 ", 12.0)],
)
def test_delta_seconds(value: object, expected: float) -> None:
    assert parse_retry_after(value) == expected


@pytest.mark.parametrize("value", [None, "", "-5", -1, "soon", "Wed, 99 Foo 2026"])
def test_absent_negative_or_unreadable_asks_for_nothing(value: object) -> None:
    assert parse_retry_after(value) is None


def test_an_http_date_is_the_seconds_until_it() -> None:
    later = datetime.now(timezone.utc) + timedelta(seconds=90)

    seconds = parse_retry_after(format_datetime(later, usegmt=True))

    assert seconds is not None
    assert 80 <= seconds <= 90


def test_an_http_date_in_the_past_asks_for_no_wait() -> None:
    earlier = datetime.now(timezone.utc) - timedelta(hours=1)

    assert parse_retry_after(format_datetime(earlier, usegmt=True)) == 0.0


def test_the_metadata_clients_use_it() -> None:
    response = Mock(spec=requests.Response)
    response.headers = {"Retry-After": "-3"}

    assert retry_after_seconds(response) is None


def test_zoteros_client_reads_retry_after_and_backoff_the_same_way() -> None:
    from zotero_cli.infra.http_client import _server_delay

    response = requests.Response()
    response.headers.update({"Retry-After": "soon", "Backoff": "4"})
    error = requests.HTTPError(response=response)

    assert _server_delay(error) == 4.0


def test_the_network_gateway_reads_an_http_date_instead_of_a_minute() -> None:
    import asyncio
    from unittest.mock import patch

    import httpx

    from zotero_cli.core.exceptions import RetryableError
    from zotero_cli.core.services.network_gateway import NetworkGateway

    later = datetime.now(timezone.utc) + timedelta(seconds=20)
    response = Mock(spec=httpx.Response)
    response.status_code = 429
    response.headers = {"Retry-After": format_datetime(later, usegmt=True)}
    gateway = NetworkGateway()

    async def fetch(*_args: object, **_kwargs: object) -> httpx.Response:
        return response

    async def go() -> RetryableError:
        with patch.object(gateway, "_fetch_validated", fetch):
            try:
                await gateway._execute_request("GET", "https://example.org/x", {})
            except RetryableError as error:
                return error
        raise AssertionError("expected a RetryableError")

    error = asyncio.run(go())

    assert 10 <= error.retry_after <= 20
