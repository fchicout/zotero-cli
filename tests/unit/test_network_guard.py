"""Issue #389: tests/unit stays off the network, and a leak can't hide."""

import socket

import pytest

from tests.network_guard import ExternalConnectionGuard, is_local_address


@pytest.mark.parametrize(
    "address",
    [("127.0.0.1", 80), ("localhost", 8000), ("::1", 443, 0, 0), ("", 9), "/tmp/a.sock", b"/tmp/a.sock"],
)
def test_local_addresses_are_allowed(address):
    assert is_local_address(address)


@pytest.mark.parametrize(
    "address",
    [("192.0.2.1", 80), ("8.8.8.8", 53), ("huggingface.co", 443), ("api.zotero.org", 443), ("2001:db8::1", 443, 0, 0)],
)
def test_anything_that_leaves_the_machine_is_refused(address):
    assert not is_local_address(address)


@pytest.fixture
def fresh_guard(monkeypatch):
    """A guard of our own, so the autouse one's record stays clean."""
    guard = ExternalConnectionGuard()
    guard.install(monkeypatch)
    return guard


def test_an_external_connect_is_refused_and_recorded(fresh_guard):
    sock = socket.socket()
    try:
        with pytest.raises(OSError, match="must stay offline"):
            sock.connect(("192.0.2.1", 80))
    finally:
        sock.close()

    assert fresh_guard.attempts == ["('192.0.2.1', 80)"]


def test_connect_ex_is_guarded_too(fresh_guard):
    sock = socket.socket()
    try:
        with pytest.raises(OSError, match="must stay offline"):
            sock.connect_ex(("198.51.100.7", 443))
    finally:
        sock.close()

    assert fresh_guard.attempts == ["('198.51.100.7', 443)"]


def test_a_loopback_connection_still_works(fresh_guard):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket()
    try:
        client.connect(server.getsockname())
    finally:
        client.close()
        server.close()

    assert fresh_guard.attempts == []


def test_a_swallowed_refusal_is_still_caught_by_the_recorder(fresh_guard):
    """Code under test often does `except Exception: ...`; the attempt must
    remain visible to the teardown check even so."""
    sock = socket.socket()
    try:
        sock.connect(("192.0.2.1", 80))
    except Exception:  # noqa: BLE001 - this is exactly the pattern being guarded against
        pass
    finally:
        sock.close()

    assert fresh_guard.attempts == ["('192.0.2.1', 80)"]


def test_the_huggingface_libraries_are_told_to_stay_offline():
    import os

    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
