"""
Keeps the unit suite off the network (Issue #389).

A unit test once downloaded an 88 MB model on every run and failed whenever
the host rate-limited us. Nothing noticed: tests/unit is meant to be fully
offline (CLAUDE.md), but nothing enforced it.

`ExternalConnectionGuard` refuses every socket connection that is not to
this machine. Code under test often wraps HTTP calls in `except Exception`,
  which would swallow the refusal and let a real leak pass silently, so the
  guard also records each attempt and the unit conftest fails the test at
  teardown if there was one.
"""

import ipaddress
import socket
from typing import Any, List

_LOCAL_NAMES = {"localhost", ""}


def is_local_address(address: Any) -> bool:
    """True for a Unix socket path or a loopback host; False for anything
    that would leave this machine."""
    if isinstance(address, (str, bytes)):
        return True  # AF_UNIX path
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host in _LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # a hostname we'd have to resolve: treat as external


class ExternalConnectionGuard:
    """Replaces `socket.socket.connect`/`connect_ex` with versions that refuse
    non-local addresses and remember having been asked."""

    def __init__(self) -> None:
        self.attempts: List[str] = []
        self._connect = socket.socket.connect
        self._connect_ex = socket.socket.connect_ex

    def install(self, monkeypatch: Any) -> None:
        guard = self

        def connect(sock: socket.socket, address: Any) -> Any:
            guard._check(address)
            return guard._connect(sock, address)

        def connect_ex(sock: socket.socket, address: Any) -> Any:
            guard._check(address)
            return guard._connect_ex(sock, address)

        monkeypatch.setattr(socket.socket, "connect", connect)
        monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)

    def _check(self, address: Any) -> None:
        if not is_local_address(address):
            self.attempts.append(str(address))
            raise OSError(f"tests/unit must stay offline: refused a connection to {address!r}")
