"""
Keeps the unit suite off the network (Issue #389).

`test_rag_full_flow` said it used the mock embedding provider but fell
through to `SentenceTransformerEmbeddingProvider`, which downloaded an 88 MB
model on every run and failed whenever Hugging Face rate-limited us. Nothing
noticed: tests/unit is meant to be fully offline (CLAUDE.md), but nothing
enforced it.

Two layers:
- `offline_env()` tells Hugging Face libraries to never go online. It runs at
  import time from the unit conftest, before any zotero_cli/huggingface
  import, because `huggingface_hub` reads the variable once, at import.
- `ExternalConnectionGuard` refuses every socket connection that is not to
  this machine. Code under test often wraps HTTP calls in `except Exception`,
  which would swallow the refusal and let a real leak pass silently, so the
  guard also records each attempt and the unit conftest fails the test at
  teardown if there was one.
"""

import ipaddress
import os
import socket
from typing import Any, List

_LOCAL_NAMES = {"localhost", ""}


def offline_env() -> None:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


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
