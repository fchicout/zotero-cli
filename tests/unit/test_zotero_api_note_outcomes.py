"""Issue #577: note writes say whether the note was stored."""

import json
from typing import Any, cast

import pytest
import requests

from zotero_cli.core.exceptions import Unavailable
from zotero_cli.core.models import WriteOutcome, WriteStatus
from zotero_cli.infra.zotero_api import ZoteroAPIClient


def response(status: int, body: Any = None, headers: dict | None = None, text: str = ""):
    res = requests.Response()
    res.status_code = status
    res.headers.update(headers or {})
    res._content = (json.dumps(body) if body is not None else text).encode()
    return res


def http_error(status: int) -> requests.exceptions.HTTPError:
    return requests.exceptions.HTTPError(response=response(status, text="no"))


class FakeSession:
    """Answers each request with the next queued reply (a Response, or an exception to raise)."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.headers: dict = {}
        self.calls: list[tuple[str, str, dict]] = []

    def _answer(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self.calls.append((method, url, kwargs))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return cast(requests.Response, reply)

    def post(self, url, **kwargs):
        return self._answer("post", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._answer("patch", url, **kwargs)

    def get(self, url, **kwargs):
        return self._answer("get", url, **kwargs)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("zotero_cli.infra.http_client.time.sleep", lambda _: None)
    return ZoteroAPIClient("key", "123", "user")


def use(client, *replies):
    session = FakeSession(*replies)
    client.http.session = session  # type: ignore[assignment]
    return session


# ---- create ----------------------------------------------------------------------------


def test_create_reports_the_stored_key_and_version(client):
    use(client, response(200, {"successful": {"0": {"key": "NOTE1", "version": 42}}}))

    outcome = client.create_note_result("PARENT", "<p>hi</p>")

    assert outcome == WriteOutcome(WriteStatus.APPLIED, 200, key="NOTE1", version=42)


def test_create_with_a_failed_entry_is_not_applied(client):
    use(client, response(200, {"failed": {"0": {"code": 400, "message": "bad note"}}}))

    outcome = client.create_note_result("PARENT", "x")

    assert outcome.status is WriteStatus.NOT_APPLIED
    assert outcome.http_status == 400
    assert "bad note" in outcome.detail


@pytest.mark.parametrize("status", [400, 403, 404, 413, 429])
def test_a_rejected_create_is_not_applied(client, status):
    use(client, *[response(status, text="rejected")] * 5)  # 429 is retried, then reported

    outcome = client.create_note_result("PARENT", "x")

    assert outcome.status is WriteStatus.NOT_APPLIED
    assert outcome.http_status == status


def test_a_server_error_after_retries_may_have_landed(client):
    use(client, *[response(503, text="down")] * 5)

    outcome = client.create_note_result("PARENT", "x")

    assert outcome.status is WriteStatus.UNKNOWN
    assert outcome.http_status == 503


@pytest.mark.parametrize(
    "failure",
    [requests.exceptions.ReadTimeout("slow"), requests.exceptions.ConnectionError("reset")],
)
def test_a_timeout_or_dropped_connection_is_unknown_not_a_failure(client, failure):
    use(client, *[failure] * 5)

    outcome = client.create_note_result("PARENT", "x")

    assert outcome.status is WriteStatus.UNKNOWN
    assert outcome.http_status is None


def test_a_duplicate_create_is_applied_and_finds_the_existing_note(client):
    duplicate = response(412, text="Precondition failed: write token already used")
    children = response(
        200,
        [{"key": "OLD1", "data": {"itemType": "note", "note": "<p>hi</p>"}}],
        {"Total-Results": "1"},
    )
    use(client, duplicate, children)

    outcome = client.create_note_result("PARENT", "<p>hi</p>")

    assert outcome.status is WriteStatus.APPLIED
    assert outcome.key == "OLD1"


def test_a_duplicate_create_is_applied_even_if_the_note_cannot_be_found(client):
    use(
        client,
        response(412, text="write token already used"),
        requests.exceptions.ConnectionError(),
    )

    outcome = client.create_note_result("PARENT", "<p>hi</p>")

    assert outcome.status is WriteStatus.APPLIED
    assert outcome.key is None


# ---- update ----------------------------------------------------------------------------


def test_update_sends_the_notes_own_version_and_reports_the_new_one(client):
    session = use(client, response(204, headers={"Last-Modified-Version": "77"}))

    outcome = client.update_note_result("N1", 70, "<p>new</p>")

    assert outcome == WriteOutcome(WriteStatus.APPLIED, 204, key="N1", version=77)
    method, url, sent = session.calls[0]
    assert method == "patch"
    assert url.endswith("/items/N1")
    assert sent["headers"]["If-Unmodified-Since-Version"] == "70"
    assert sent["json"] == {"note": "<p>new</p>"}


def test_update_can_move_the_note_to_a_parent(client):
    session = use(client, response(204))

    client.update_note_result("N1", 70, "x", parent_item_key="P1")

    assert session.calls[0][2]["json"]["parentItem"] == "P1"


def test_an_unknown_version_is_looked_up_first(client):
    item = {"key": "N1", "version": 55, "data": {"key": "N1", "version": 55, "itemType": "note"}}
    session = use(client, response(200, item), response(204))

    outcome = client.update_note_result("N1", 0, "x")

    assert outcome.status is WriteStatus.APPLIED
    assert [c[0] for c in session.calls] == ["get", "patch"]
    assert session.calls[1][2]["headers"]["If-Unmodified-Since-Version"] == "55"


def test_an_unknown_version_for_a_missing_note_is_not_applied(client):
    use(client, response(404, text="gone"))

    assert client.update_note_result("N1", 0, "x").status is WriteStatus.NOT_APPLIED


def test_a_412_is_a_conflict_and_sends_one_request(client):
    session = use(client, response(412, text="changed"))

    outcome = client.update_note_result("N1", 70, "x")

    assert outcome.status is WriteStatus.CONFLICT
    assert outcome.http_status == 412
    assert len(session.calls) == 1


def test_retry_on_conflict_rereads_the_version_and_writes_once_more(client):
    item = {"key": "N1", "version": 90, "data": {"key": "N1", "version": 90, "itemType": "note"}}
    session = use(
        client,
        response(412),
        response(200, item),
        response(204, headers={"Last-Modified-Version": "91"}),
    )

    outcome = client.update_note_result("N1", 70, "x", retry_on_conflict=True)

    assert outcome == WriteOutcome(WriteStatus.APPLIED, 204, key="N1", version=91)
    assert [c[0] for c in session.calls] == ["patch", "get", "patch"]
    assert session.calls[2][2]["headers"]["If-Unmodified-Since-Version"] == "90"


def test_retry_on_conflict_reports_a_second_conflict(client):
    item = {"key": "N1", "version": 90, "data": {"key": "N1", "version": 90, "itemType": "note"}}
    use(client, response(412), response(200, item), response(412))

    outcome = client.update_note_result("N1", 70, "x", retry_on_conflict=True)

    assert outcome.status is WriteStatus.CONFLICT


def test_retry_on_conflict_with_a_deleted_note_is_not_applied(client):
    use(client, response(412), response(404, text="gone"))

    outcome = client.update_note_result("N1", 70, "x", retry_on_conflict=True)

    assert outcome.status is WriteStatus.NOT_APPLIED


@pytest.mark.parametrize(
    "status, expected", [(403, WriteStatus.NOT_APPLIED), (404, WriteStatus.NOT_APPLIED)]
)
def test_a_rejected_update_is_not_applied(client, status, expected):
    use(client, response(status, text="no"))

    assert client.update_note_result("N1", 70, "x").status is expected


def test_an_update_whose_connection_drops_is_unknown(client):
    use(client, *[requests.exceptions.ConnectionError("reset")] * 5)

    assert client.update_note_result("N1", 70, "x").status is WriteStatus.UNKNOWN


def test_a_failure_detail_never_carries_the_api_key(client, monkeypatch):
    from zotero_cli.core import logging_config

    monkeypatch.setattr(logging_config, "_secrets", set())
    logging_config.register_secrets("sekrit-api-key-value")
    client.http = _Raising(Unavailable("boom with sekrit-api-key-value inside"))

    outcome = client.update_note_result("N1", 70, "x")

    assert "sekrit-api-key-value" not in outcome.detail
    assert outcome.status is WriteStatus.UNKNOWN


class _Raising:
    last_library_version = 0

    def __init__(self, error: Exception) -> None:
        self.error = error

    def patch(self, *args, **kwargs):
        raise self.error


# ---- the boolean methods ride on the outcomes ------------------------------------------------


def test_the_boolean_methods_are_true_only_when_applied(client):
    use(client, response(204), response(412), response(200, {"successful": {"0": {"key": "N"}}}))

    assert client.update_note("N1", 70, "x") is True
    assert client.update_note("N1", 70, "x") is False
    assert client.create_note("P", "x") is True
