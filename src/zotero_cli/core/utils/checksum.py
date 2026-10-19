import hashlib
from typing import IO

_CHUNK_BYTES = 4096


def sha256_stream(stream: IO[bytes]) -> str:
    """Hex SHA-256 of a binary stream, read in chunks."""
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(_CHUNK_BYTES), b""):
        digest.update(block)
    return digest.hexdigest()
