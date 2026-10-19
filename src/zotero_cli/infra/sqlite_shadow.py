"""The process-wide shadow copy of zotero.sqlite and the per-thread connections to it
(Issue #436), used by the offline gateway so it never locks Zotero Desktop's database."""

import atexit
import os
import shutil
import sqlite3
import tempfile
import threading
from typing import Dict, List, Optional, Tuple

# --- One shadow copy per process (Issue #436) ---
#
# Every service builds its own gateway, and each used to copy the whole
# database (2 x 842 MB for `slr report status`) and open a connection per
# call (12,218 for one export). The copy is now shared by every gateway and
# keyed by the file's identity, so a changed database (after `item trash`)
# is copied again.
_shadow_lock = threading.Lock()
_shadows: Dict[Tuple[str, int, int], str] = {}
# One connection per thread to the current copy, shared by every gateway
# (`serve` runs handlers in a threadpool; a connection stays in its thread).
_thread_state = threading.local()
# (shadow path, connection): lets a stale path's connections be closed
# before its directory is removed (Issue #413: shutil.rmtree silently
# failed on Windows, which can't delete a file a connection still has
# open, leaking the old copy on every database change).
_all_connections: List[Tuple[str, sqlite3.Connection]] = []


def _shadow_parent() -> Optional[str]:
    """A private directory in the user's cache, on disk: /tmp is tmpfs on
    Fedora and Arch, where each copy would sit in RAM. None falls back to
    the system temp directory."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    path = os.path.join(base, "zotero-cli")
    try:
        os.makedirs(path, mode=0o700, exist_ok=True)
        if os.name != "nt":
            os.chmod(path, 0o700)
    except OSError:
        return None
    return path


def _shadow_copy(database_path: str) -> str:
    """The process-wide copy of `database_path`, made on first use."""
    real = os.path.realpath(database_path)
    st = os.stat(real)
    key = (real, st.st_mtime_ns, st.st_size)
    with _shadow_lock:
        cached = _shadows.get(key)
        if cached and os.path.exists(cached):
            return cached
        for old in [k for k in _shadows if k[0] == real]:
            stale_path = _shadows.pop(old)
            _close_connections_for(stale_path)
            shutil.rmtree(os.path.dirname(stale_path), ignore_errors=True)
        # Non-predictable temp path (Issue #240) - a manually joined
        # tempfile.gettempdir()/f"zotero_cli_shadow_{os.getpid()}.sqlite"
        # path is deterministic (PID space is bounded/reused), letting
        # a local attacker on a shared host pre-plant a symlink there.
        # The copy is the user's whole Zotero database, so it lives in a
        # mkdtemp() directory (0700) as a file created 0600 - copying
        # the source's mode (shutil.copy2) left it world-readable - and
        # is removed at exit. A plain file copy, since Zotero Desktop
        # holds an exclusive lock on the live database while it runs.
        temp_dir = tempfile.mkdtemp(prefix="zotero_cli_shadow_", dir=_shadow_parent())
        temp_path = os.path.join(temp_dir, "zotero.sqlite")
        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as dst, open(real, "rb") as src:
            shutil.copyfileobj(src, dst)
        _shadows[key] = temp_path
        return temp_path


def _shadow_connection(database_path: str) -> Tuple[sqlite3.Connection, str]:
    """This thread's connection to the current copy of `database_path`."""
    path = _shadow_copy(database_path)
    conns: Dict[str, Tuple[sqlite3.Connection, str]] = getattr(_thread_state, "conns", {})
    _thread_state.conns = conns
    cached = conns.get(database_path)
    if cached is not None and cached[1] == path:
        return cached
    if cached is not None:
        cached[0].close()  # the database changed and was copied again
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    with _shadow_lock:
        _all_connections.append((path, conn))
    conns[database_path] = (conn, path)
    return conn, path


def _close_connections_for(path: str) -> None:
    """Closes and forgets every open connection to `path` from the calling
    thread (caller holds _shadow_lock). Windows can't delete a file a
    connection still has open. sqlite3 refuses to close a connection from a
    thread other than the one that opened it (silently, via the same
    sqlite3.Error catch every close here already uses) - a connection held
    open by another thread when the database changes can still block the
    old copy's removal there; the file is cleaned up at exit either way."""
    remaining = []
    for entry_path, conn in _all_connections:
        if entry_path == path:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        else:
            remaining.append((entry_path, conn))
    _all_connections[:] = remaining


def _cleanup_shadows() -> None:
    with _shadow_lock:
        for path in _shadows.values():
            _close_connections_for(path)
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)
        _shadows.clear()


atexit.register(_cleanup_shadows)
