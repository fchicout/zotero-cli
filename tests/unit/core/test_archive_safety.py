import io
import json
import zipfile

import pytest

from zotero_cli.core.utils import archive_safety
from zotero_cli.core.utils.archive_safety import (
    ArchiveLimitError,
    check_entry_count,
    copy_member,
    read_json_member,
)


def _zip(entries, compression=zipfile.ZIP_LZMA):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=compression) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    buf.seek(0)
    return zipfile.ZipFile(buf)


def test_read_json_member_within_limit():
    zf = _zip({"data.json": json.dumps([{"key": "A"}])})
    assert read_json_member(zf, "data.json") == [{"key": "A"}]


def test_highly_compressible_entry_is_refused_before_it_fills_memory():
    """A few KB of LZMA that declares/expands to far more than the limit."""
    zf = _zip({"data.json": b"[" + b" " * (5 * 1024 * 1024) + b"]"})
    assert len(zf.fp.getvalue()) < 100_000  # small archive...
    with pytest.raises(ArchiveLimitError):
        read_json_member(zf, "data.json", max_bytes=1024 * 1024)  # ...too big when expanded


def test_lying_size_header_never_yields_more_than_the_limit():
    """A crafted header understating the size: zipfile itself stops at the
    declared size (and fails the CRC check); the streaming counter is a
    second line of defence. Either way nothing past the limit is kept."""
    zf = _zip({"file.pdf": b"%PDF" + b"x" * 10_000})
    zf.getinfo("file.pdf").file_size = 10
    out = io.BytesIO()
    with pytest.raises((ArchiveLimitError, zipfile.BadZipFile)):
        copy_member(zf, "file.pdf", out, max_bytes=1000)
    assert len(out.getvalue()) <= 1000


def test_streaming_counter_stops_past_the_limit(monkeypatch):
    """Even if a member yields more than its declared size, copying stops."""
    zf = _zip({"file.pdf": b"x" * 5000})
    monkeypatch.setattr(archive_safety, "_CHUNK", 1000)
    zf.getinfo("file.pdf").file_size = 100  # pass the declared-size check...
    real_open = zf.open

    class Endless(io.RawIOBase):
        def readable(self):
            return True

        def readinto(self, b):
            b[: len(b)] = b"x" * len(b)
            return len(b)

    monkeypatch.setattr(zf, "open", lambda *a, **k: io.BufferedReader(Endless()))
    out = io.BytesIO()
    with pytest.raises(ArchiveLimitError):
        copy_member(zf, "file.pdf", out, max_bytes=2500)  # ...but the data keeps coming
    assert len(out.getvalue()) <= 2500
    assert real_open  # the real opener is untouched outside this test


def test_too_many_entries(monkeypatch):
    monkeypatch.setattr(archive_safety, "MAX_ARCHIVE_ENTRIES", 3)
    zf = _zip({f"f{i}": b"x" for i in range(4)})
    with pytest.raises(ArchiveLimitError):
        check_entry_count(zf)
