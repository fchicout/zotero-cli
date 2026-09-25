"""Issue #365: the unit suite must never touch the developer's real config
directory. These tests fail if the isolation in tests/unit/conftest.py is
removed or bypassed."""

import os
from pathlib import Path

from tests.home_isolation import real_home


def _test_home() -> Path:
    return Path(os.environ["ZOTERO_CLI_TEST_HOME"])


def test_storage_dir_is_inside_the_temporary_test_home():
    from zotero_cli.core.config import get_storage_dir

    storage = get_storage_dir().resolve()
    assert _test_home().resolve() in storage.parents
    assert real_home().resolve() not in storage.parents or real_home() == _test_home()


def test_home_and_config_env_point_at_the_test_home():
    assert Path.home() == _test_home()
    assert Path(os.environ["XDG_CONFIG_HOME"]).is_relative_to(_test_home())
    assert Path(os.environ["APPDATA"]).is_relative_to(_test_home())


def test_config_manager_default_path_is_isolated():
    """test_rag_model_set wrote the real config through this default."""
    from zotero_cli.core.config import ConfigLoader

    assert ConfigLoader().config_path.resolve().is_relative_to(_test_home().resolve())


def test_no_real_zotero_credentials_leak_into_tests():
    for key in ("ZOTERO_API_KEY", "ZOTERO_LIBRARY_ID", "ZOTERO_USER_ID"):
        assert key not in os.environ
