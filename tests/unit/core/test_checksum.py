import hashlib
import io

from zotero_cli.core.utils.checksum import sha256_stream


def test_sha256_stream_matches_hashlib_across_chunk_boundaries() -> None:
    data = bytes(range(256)) * 50 + b"tail"

    assert sha256_stream(io.BytesIO(data)) == hashlib.sha256(data).hexdigest()


def test_sha256_stream_of_nothing_is_the_empty_digest() -> None:
    assert sha256_stream(io.BytesIO(b"")) == hashlib.sha256(b"").hexdigest()
