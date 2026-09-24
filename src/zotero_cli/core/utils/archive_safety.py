"""
Size limits for reading .zaf backup archives.

A .zaf is a ZIP (usually LZMA-compressed) that a collaborator may hand
you, so its contents are untrusted: a small archive can declare or expand
into enormous entries. Every read goes through these helpers, which check
the declared size first and then count the bytes actually decompressed,
so a lying header can't get past the limit either.
"""

import json
import zipfile
from typing import IO, Any

MAX_ARCHIVE_ENTRIES = 200_000
MAX_JSON_BYTES = 256 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 1024 * 1024 * 1024
_CHUNK = 1024 * 1024


class ArchiveLimitError(ValueError):
    """Raised when an archive or one of its entries exceeds a size limit."""


def check_entry_count(zf: zipfile.ZipFile) -> None:
    count = len(zf.infolist())
    if count > MAX_ARCHIVE_ENTRIES:
        raise ArchiveLimitError(
            f"Archive has {count} entries, more than the {MAX_ARCHIVE_ENTRIES} allowed"
        )


def copy_member(zf: zipfile.ZipFile, name: str, dst: IO[bytes], max_bytes: int) -> int:
    """Streams entry `name` into `dst`, stopping with ArchiveLimitError once
    more than `max_bytes` have been decompressed. Returns the bytes copied."""
    info = zf.getinfo(name)
    if info.file_size > max_bytes:
        raise ArchiveLimitError(
            f"{name} is {info.file_size} bytes, more than the {max_bytes}-byte limit"
        )
    total = 0
    with zf.open(info) as src:
        while chunk := src.read(_CHUNK):
            total += len(chunk)
            if total > max_bytes:
                raise ArchiveLimitError(f"{name} expands past the {max_bytes}-byte limit")
            dst.write(chunk)
    return total


def read_json_member(zf: zipfile.ZipFile, name: str, max_bytes: int = MAX_JSON_BYTES) -> Any:
    """Reads and parses JSON entry `name` within `max_bytes`."""
    import io

    buffer = io.BytesIO()
    copy_member(zf, name, buffer, max_bytes)
    return json.loads(buffer.getvalue().decode("utf-8"))
