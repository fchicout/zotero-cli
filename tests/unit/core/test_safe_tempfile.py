import os

from zotero_cli.core.utils.safe_tempfile import write_secure_temp_file


def test_write_secure_temp_file_writes_content_and_returns_path():
    path = write_secure_temp_file(b"%PDF-1.4 hello", prefix="test_", suffix=".pdf")
    try:
        assert path.exists()
        assert path.read_bytes() == b"%PDF-1.4 hello"
        assert path.name.startswith("test_")
        assert path.name.endswith(".pdf")
    finally:
        os.remove(path)


def test_write_secure_temp_file_produces_non_predictable_names():
    """Issue #240: two calls with the same prefix must not collide or be
    derivable from any caller-provided value alone."""
    path1 = write_secure_temp_file(b"a", prefix="same_prefix_", suffix=".pdf")
    path2 = write_secure_temp_file(b"b", prefix="same_prefix_", suffix=".pdf")
    try:
        assert path1 != path2
    finally:
        os.remove(path1)
        os.remove(path2)


def test_write_secure_temp_file_created_with_owner_only_permissions():
    """tempfile.mkstemp creates the file with mode 0600 - unlike a plain
    write to a manually joined predictable path, an attacker who somehow
    predicted the name still couldn't read it before it's moved/uploaded."""
    path = write_secure_temp_file(b"secret-ish", prefix="perm_test_", suffix=".pdf")
    try:
        mode = os.stat(path).st_mode & 0o777
        assert mode == 0o600
    finally:
        os.remove(path)
