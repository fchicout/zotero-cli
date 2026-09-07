"""
Shared helper for writing a downloaded PDF (or other binary payload) to a
non-predictable temp-file path (Issue #240).

Several call sites built a temp path by manually joining
`tempfile.gettempdir()` with a fully deterministic filename derived from
an item key (e.g. `f"openalex_{item.key}.pdf"`). On a shared multi-user
host with a world-writable /tmp, a local attacker could pre-create a
symlink at that guessable path pointing at a victim-owned file - the
subsequent write would then follow the symlink and overwrite it.
`tempfile.mkstemp` creates the file itself (O_CREAT|O_EXCL, mode 0600),
so there's no path for an attacker to have pre-planted anything at it.
"""

import os
import tempfile
from pathlib import Path


def write_secure_temp_file(content: bytes, prefix: str, suffix: str = "") -> Path:
    """Writes `content` to a newly created, non-predictable temp file and
    returns its path."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
    except BaseException:
        os.remove(path)
        raise
    return Path(path)
