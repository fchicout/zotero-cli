import os
import stat
from unittest.mock import patch

import pytest
import toml

from zotero_cli.core.config import ConfigManager


def test_config_manager_save_group_context(tmp_path):
    config_file = tmp_path / "config.toml"

    # Create initial config
    initial_data = {
        "zotero": {
            "api_key": "secret",
            "library_id": "old_lib",
            "library_type": "user",
            "user_id": "123",
        }
    }
    with open(config_file, "w") as f:
        toml.dump(initial_data, f)

    with patch("zotero_cli.core.config.ConfigLoader") as MockLoader:
        MockLoader.return_value.config_path = config_file

        manager = ConfigManager(config_path=config_file)
        manager.save_group_context("999")

        with open(config_file, "r") as f:
            new_data = toml.load(f)

        assert new_data["zotero"]["library_id"] == "999"
        assert new_data["zotero"]["library_type"] == "group"
        assert new_data["zotero"]["api_key"] == "secret"  # Preserved


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_config_manager_update_config_writes_0600_permissions(tmp_path):
    """Issue #236: config.toml holds live API keys - it must not inherit
    the process umask and end up world-readable."""
    config_file = tmp_path / "subdir" / "config.toml"

    with patch("zotero_cli.core.config.ConfigLoader") as MockLoader:
        MockLoader.return_value.config_path = config_file

        manager = ConfigManager(config_path=config_file)
        manager.update_config({"api_key": "super-secret"})

    file_mode = stat.S_IMODE(config_file.stat().st_mode)
    assert file_mode == 0o600

    dir_mode = stat.S_IMODE(config_file.parent.stat().st_mode)
    assert dir_mode == 0o700


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_config_manager_update_config_fixes_permissions_on_existing_world_readable_file(tmp_path):
    """A pre-#236 config.toml that's already world-readable must be
    tightened the next time it's written, not left as-is."""
    config_file = tmp_path / "config.toml"
    with open(config_file, "w") as f:
        toml.dump({"zotero": {"api_key": "secret"}}, f)
    config_file.chmod(0o644)

    with patch("zotero_cli.core.config.ConfigLoader") as MockLoader:
        MockLoader.return_value.config_path = config_file
        manager = ConfigManager(config_path=config_file)
        manager.update_config({"library_id": "999"})

    file_mode = stat.S_IMODE(config_file.stat().st_mode)
    assert file_mode == 0o600


def test_config_manager_file_not_found(tmp_path):
    """A path whose parent can't be created (not a permissions probe: mkdir's
    own parents=True would happily create any writable-tree path, and a
    hardcoded unwritable root location doesn't behave the same on every OS -
    Linux raises FileNotFoundError/PermissionError, macOS's read-only system
    volume raises a plain OSError). A regular file standing where a
    directory needs to go raises NotADirectoryError identically everywhere.
    """
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x", encoding="utf-8")
    manager = ConfigManager(config_path=blocker / "sub" / "path.toml")

    # POSIX raises NotADirectoryError (ENOTDIR); Windows' CreateDirectory
    # reports the same "something's already there" case as "already exists"
    # (FileExistsError, WinError 183) instead.
    with pytest.raises((NotADirectoryError, FileExistsError)):
        manager.save_group_context("123")
