"""Issue #409: a POST that creates objects must not create them twice when a
retry follows a write the server already committed."""

from typing import Any, Dict, List
from unittest.mock import Mock

import pytest
import requests

from zotero_cli.infra.http_client import IDEMPOTENCY_HEADER, ZoteroHttpClient
from zotero_cli.infra.zotero_api import ZoteroAPIClient


class CommitThenDropSession:
    """Commits the first write, then loses the connection before answering;
    answers the retry like Zotero does for a token it has already seen."""

    def __init__(self, fail_with: Exception):
        self.headers: Dict[str, str] = {}
        self.calls: List[Dict[str, Any]] = []
        self.created = 0
        self.seen_tokens: set = set()
        self.fail_with = fail_with

    def post(self, url, json=None, headers=None, timeout=None):
        token = headers.get(IDEMPOTENCY_HEADER)
        self.calls.append({"token": token, "timeout": timeout})
        if token in self.seen_tokens:
            response = Mock(status_code=412, text="Write token already used", headers={})
            return response
        self.seen_tokens.add(token)
        self.created += len(json)
        if len(self.calls) == 1:
            raise self.fail_with
        response = Mock(status_code=200, headers={}, text="")
        response.json.return_value = {"successful": {"0": {"key": "NEW1"}}}
        return response


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    monkeypatch.setattr(
        ZoteroHttpClient._post_with_retries.retry,  # type: ignore[attr-defined]
        "sleep",
        lambda _s: None,
    )


@pytest.mark.parametrize(
    "failure",
    [requests.exceptions.ConnectionError("reset"), requests.exceptions.ReadTimeout("slow")],
)
def test_retry_after_a_committed_write_creates_nothing_twice(failure):
    client = ZoteroAPIClient("key", "123", "user")
    session = CommitThenDropSession(failure)
    client.http.session = session  # type: ignore[assignment]

    result = client.create_note("PARENT", "hello")

    assert session.created == 1  # the retry was recognised, not re-applied
    assert len(session.calls) == 2
    tokens = {c["token"] for c in session.calls}
    assert len(tokens) == 1 and None not in tokens and len(tokens.pop()) == 32
    assert all(c["timeout"] for c in session.calls)
    assert result is False  # created, but its key isn't known: reported, not duplicated


def test_each_logical_post_gets_its_own_token():
    http = ZoteroHttpClient("key", "123", "user")
    tokens = []

    def post(url, json=None, headers=None, timeout=None):
        tokens.append(headers.get(IDEMPOTENCY_HEADER))
        response = Mock(status_code=200, headers={}, text="")
        response.raise_for_status.return_value = None
        return response

    http.session = Mock(headers={}, post=post)
    http.post("items", json_data=[{"itemType": "note"}])
    http.post("items", json_data=[{"itemType": "note"}])

    assert tokens[0] and tokens[1] and tokens[0] != tokens[1]


def test_a_non_creating_post_has_no_write_token():
    http = ZoteroHttpClient("key", "123", "user")
    seen = {}

    def post(url, json=None, headers=None, timeout=None):
        seen.update(headers)
        response = Mock(status_code=200, headers={}, text="")
        response.raise_for_status.return_value = None
        return response

    http.session = Mock(headers={}, post=post)
    http.post("keys", json_data={"not": "a list"}, use_prefix=False)

    assert IDEMPOTENCY_HEADER not in seen


def test_a_version_conflict_412_still_raises():
    """A 412 about a version precondition is an error, not a duplicate write."""
    http = ZoteroHttpClient("key", "123", "user")
    conflict = requests.Response()
    conflict.status_code = 412
    conflict._content = b"Library has been modified since the specified version"
    http.session = Mock(headers={}, post=Mock(return_value=conflict))

    with pytest.raises(requests.exceptions.HTTPError):
        http.post("items", json_data=[{}], version_check=True)
