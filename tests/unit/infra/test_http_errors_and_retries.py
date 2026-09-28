"""Issues #369 and #398: requests time out, retries are bounded and honour
Retry-After, and a final failure is a typed error, not a hang or an empty
result."""

from unittest.mock import Mock

import pytest
import requests

from zotero_cli.core.exceptions import AuthError, Conflict, NotFound, Unavailable, ZoteroCliError
from zotero_cli.infra import http_client
from zotero_cli.infra.http_client import MAX_ATTEMPTS, ZoteroHttpClient


@pytest.fixture
def sleeps(monkeypatch):
    waited: list[float] = []
    for method in ("_get_with_retries", "_write_with_retries", "_post_with_retries"):
        monkeypatch.setattr(
            getattr(ZoteroHttpClient, method).retry,  # type: ignore[attr-defined]
            "sleep",
            waited.append,
        )
    return waited


def _response(status, headers=None):
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    response._content = b"{}"
    return response


def _client(session_get):
    client = ZoteroHttpClient("key", "123", "user")
    client.session = Mock(headers={}, get=session_get)
    return client


def test_every_get_has_a_timeout(sleeps):
    get = Mock(return_value=_response(200))
    _client(get).get("items")
    assert get.call_args.kwargs["timeout"] == http_client.REQUEST_TIMEOUT


def test_network_failure_is_bounded_and_ends_as_unavailable(sleeps, capsys):
    get = Mock(side_effect=requests.exceptions.ConnectionError("unreachable"))

    with pytest.raises(Unavailable, match="check your network"):
        _client(get).get("tags")

    assert get.call_count == MAX_ATTEMPTS
    assert len(sleeps) == MAX_ATTEMPTS - 1
    # One notice, not one per retry.
    assert capsys.readouterr().err.count("retrying") == 1


def test_timeouts_are_retried_then_unavailable(sleeps):
    get = Mock(side_effect=requests.exceptions.ReadTimeout("slow"))
    with pytest.raises(Unavailable):
        _client(get).get("tags")
    assert get.call_count == MAX_ATTEMPTS


def test_retry_after_is_honoured(sleeps):
    get = Mock(side_effect=[_response(429, {"Retry-After": "7"}), _response(200)])

    _client(get).get("items")

    assert sleeps == [7.0]


def test_backoff_header_pauses_the_next_request(sleeps, monkeypatch):
    paused: list[float] = []
    monkeypatch.setattr(http_client.time, "sleep", paused.append)
    get = Mock(side_effect=[_response(200, {"Backoff": "3"}), _response(200)])
    client = _client(get)

    client.get("items")
    client.get("items")

    assert len(paused) == 1 and 0 < paused[0] <= 3


@pytest.mark.parametrize(
    "status, error, code",
    [
        (401, AuthError, 4),
        (403, AuthError, 4),
        (404, NotFound, 3),
        (412, Conflict, 6),
        (500, Unavailable, 5),
        (503, Unavailable, 5),
        (400, ZoteroCliError, 1),
    ],
)
def test_http_status_maps_to_a_typed_error(sleeps, status, error, code):
    get = Mock(return_value=_response(status))

    with pytest.raises(error) as raised:
        _client(get).get("items/K1")

    assert raised.value.exit_code == code


def test_auth_error_says_what_to_do(sleeps):
    with pytest.raises(AuthError, match="zotero-cli init"):
        _client(Mock(return_value=_response(403))).get("items")


def test_patch_and_delete_keep_returning_412_to_the_caller(sleeps):
    client = ZoteroHttpClient("key", "123", "user")
    client.session = Mock(headers={}, patch=Mock(return_value=_response(412)),
                          delete=Mock(return_value=_response(412)))

    assert client.patch("items/K1", {}).status_code == 412
    assert client.delete("items/K1", version=3).status_code == 412
    assert client.session.delete.call_args.kwargs["timeout"] == http_client.REQUEST_TIMEOUT
