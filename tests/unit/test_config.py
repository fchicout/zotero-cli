import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from zotero_cli.core.config import ConfigLoader, ZoteroConfig, get_config, reset_config
from zotero_cli.core.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def _reset_global_config_cache():
    """get_config()'s module-global cache must not leak state between
    tests in this file."""
    reset_config()
    yield
    reset_config()


def test_config_loader_default_path():
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/config"}):
        loader = ConfigLoader()
        assert loader.config_path == Path("/tmp/config/zotero-cli/config.toml")


def test_load_from_env_only(tmp_path):
    config_file = tmp_path / "config.toml"
    # No file exists

    env = {
        "ZOTERO_API_KEY": "env_key",
        "ZOTERO_USER_ID": "env_user",
        "ZOTERO_LIBRARY_ID": "env_lib",
    }

    with patch.dict(os.environ, env):
        loader = ConfigLoader(config_path=config_file)
        config = loader.load()
        assert config.api_key == "env_key"
        assert config.user_id == "env_user"
        assert config.library_id == "env_lib"


def test_load_from_file_only(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as f:
        f.write('[zotero]\napi_key = "file_key"\nuser_id = "file_user"\nlibrary_id = "file_lib"\n')

    # Ensure env is empty for these keys
    with patch.dict(os.environ, {}, clear=True):
        loader = ConfigLoader(config_path=config_file)
        config = loader.load()
        assert config.api_key == "file_key"
        assert config.user_id == "file_user"
        assert config.library_id == "file_lib"


def test_load_rejects_invalid_library_type_in_file(tmp_path):
    """Regression test for Issue #300: a typo'd library_type (e.g.
    'personal') must fail fast at config-load time with a clear message,
    not silently fall through to infra/http_client.py's "anything but
    'user' means 'group'" behavior and surface as a confusing 404/403."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[zotero]\napi_key = "k"\nlibrary_type = "personal"\n')

    with patch.dict(os.environ, {}, clear=True):
        loader = ConfigLoader(config_path=config_file)
        with pytest.raises(ConfigurationError, match="library_type"):
            loader.load()


def test_load_rejects_invalid_library_type_from_env(tmp_path):
    config_file = tmp_path / "config.toml"
    # No file needed - env takes precedence anyway.

    with patch.dict(os.environ, {"ZOTERO_LIBRARY_TYPE": "Group"}, clear=True):
        loader = ConfigLoader(config_path=config_file)
        with pytest.raises(ConfigurationError, match="library_type"):
            loader.load()


def test_load_accepts_valid_library_type_values(tmp_path):
    config_file = tmp_path / "config.toml"

    with patch.dict(os.environ, {}, clear=True):
        for value in ("user", "group"):
            config_file.write_text(f'[zotero]\napi_key = "k"\nlibrary_type = "{value}"\n')
            loader = ConfigLoader(config_path=config_file)
            assert loader.load().library_type == value


def test_load_from_file_malformed_toml_raises_configuration_error(tmp_path):
    """Regression test for Issue #290: a TOML syntax error must raise
    ConfigurationError with the real cause, not be silently swallowed to
    an empty config that fails confusingly several layers deeper."""
    config_file = tmp_path / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("[zotero\napi_key = this is not valid toml")

    with patch.dict(os.environ, {}, clear=True):
        loader = ConfigLoader(config_path=config_file)
        with pytest.raises(ConfigurationError, match=str(config_file)):
            loader.load()


def test_load_from_file_unreadable_degrades_to_empty_config(tmp_path):
    """A genuinely unreadable file (permissions, OS-level failure) keeps
    the pre-existing degrade-to-empty-config behavior - only a parse
    failure (bad TOML content) should now raise."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[zotero]\napi_key = "file_key"\n')

    with patch.dict(os.environ, {}, clear=True):
        loader = ConfigLoader(config_path=config_file)
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            config = loader.load()
        assert config.api_key is None


def test_precedence_env_over_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as f:
        f.write('[zotero]\napi_key = "file_key"\nuser_id = "file_user"\n')

    env = {"ZOTERO_API_KEY": "env_key"}

    # Use clear=True to prevent outside env vars (like those injected by Infisical CLI) from polluting the config loader's resolution
    with patch.dict(os.environ, env, clear=True):
        loader = ConfigLoader(config_path=config_file)
        config = loader.load()
        assert config.api_key == "env_key"  # Env wins
        assert config.user_id == "file_user"  # File falls back


def test_resolve_library_target_explicit_library_id():
    config = ZoteroConfig(api_key="k", library_id="123", library_type="group")
    assert config.resolve_library_target() == ("123", "group")


def test_resolve_library_target_force_user():
    config = ZoteroConfig(api_key="k", library_id="123", library_type="group", user_id="u1")
    assert config.resolve_library_target(force_user=True) == ("u1", "user")


def test_resolve_library_target_force_user_no_user_id_falls_through():
    config = ZoteroConfig(api_key="k", user_id=None)
    with pytest.raises(ConfigurationError):
        config.resolve_library_target(force_user=True, require_group=True)


def test_resolve_library_target_force_user_no_user_id_non_required():
    config = ZoteroConfig(api_key="k", user_id=None)
    assert config.resolve_library_target(force_user=True, require_group=False) == ("0", "user")


def test_resolve_library_target_group_url_parsed():
    config = ZoteroConfig(
        api_key="k",
        library_id=None,
        library_type="",
        target_group_url="https://www.zotero.org/groups/456/items",
    )
    assert config.resolve_library_target() == ("456", "group")


def test_resolve_library_target_group_url_unparseable():
    config = ZoteroConfig(
        api_key="k",
        library_id=None,
        library_type="",
        target_group_url="https://www.zotero.org/not-a-group-url",
    )
    with pytest.raises(ConfigurationError):
        config.resolve_library_target()


def test_resolve_library_target_user_id_fallback():
    config = ZoteroConfig(api_key="k", library_id=None, library_type="", user_id="u2")
    assert config.resolve_library_target() == ("u2", "user")


def test_resolve_library_target_no_library_defined_required():
    config = ZoteroConfig(api_key="k", library_id=None, library_type="", user_id=None)
    with pytest.raises(ConfigurationError):
        config.resolve_library_target(require_group=True)


def test_resolve_library_target_no_library_defined_not_required():
    config = ZoteroConfig(api_key="k", library_id=None, library_type="", user_id=None)
    assert config.resolve_library_target(require_group=False) == ("0", "user")


def test_resolve_scoping_id_defaults_to_library_id():
    config = ZoteroConfig(api_key="k", library_id="123", user_id="u1")
    assert config.resolve_scoping_id() == "123"


def test_resolve_scoping_id_force_user_prefers_user_id():
    """Issue #257: --user must apply to purely-local storage scoping
    (job queue, snowball discovery graph), not just the online gateway."""
    config = ZoteroConfig(api_key="k", library_id="123", user_id="u1")
    assert config.resolve_scoping_id(force_user=True) == "u1"


def test_resolve_scoping_id_falls_back_to_default():
    config = ZoteroConfig(api_key="k", library_id=None, user_id=None)
    assert config.resolve_scoping_id() == "default"
    assert config.resolve_scoping_id(force_user=True) == "default"


def test_resolve_scoping_id_default_fallback_logs_a_warning(caplog):
    """Regression test for Issue #296: falling back to the shared
    'default' storage scope must be logged, not silent - it's a real
    data-mixing footgun (job queue / discovery graph shared across
    otherwise-unrelated under-configured sessions)."""
    config = ZoteroConfig(api_key="k", library_id=None, user_id=None)

    with caplog.at_level("WARNING"):
        config.resolve_scoping_id()

    assert any("default" in r.message for r in caplog.records)


def test_resolve_scoping_id_no_warning_when_library_id_resolves(caplog):
    config = ZoteroConfig(api_key="k", library_id="123", user_id="u1")

    with caplog.at_level("WARNING"):
        config.resolve_scoping_id()

    assert caplog.records == []


def test_get_config_caches_across_calls_with_no_path(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[zotero]\napi_key = "k1"\n')

    with patch.dict(os.environ, {}, clear=True):
        first = get_config(str(config_file))
        # A second no-path call must return the cached instance, not reload.
        config_file.write_text('[zotero]\napi_key = "k2"\n')
        second = get_config()

    assert first is second
    assert second.api_key == "k1"


def test_get_config_reloads_when_path_given(tmp_path):
    config_a = tmp_path / "a.toml"
    config_a.write_text('[zotero]\napi_key = "a"\n')
    config_b = tmp_path / "b.toml"
    config_b.write_text('[zotero]\napi_key = "b"\n')

    with patch.dict(os.environ, {}, clear=True):
        first = get_config(str(config_a))
        second = get_config(str(config_b))

    assert first.api_key == "a"
    assert second.api_key == "b"


def test_get_config_concurrent_calls_do_not_corrupt_the_cache(tmp_path):
    """Regression test for Issue #301: get_config()'s read-modify-write of
    the module-global cache had no lock - concurrent callers (e.g.
    serve's threadpool-offloaded routes) could observe a torn/partial
    state. Hammer it from many threads with differing config_path
    arguments and confirm every call returns a fully-formed, internally
    consistent ZoteroConfig with no exception."""
    config_files = []
    for i in range(5):
        path = tmp_path / f"config_{i}.toml"
        path.write_text(f'[zotero]\napi_key = "key_{i}"\nlibrary_id = "lib_{i}"\n')
        config_files.append(path)

    results = []
    errors = []
    barrier = threading.Barrier(20)

    def worker(path):
        try:
            barrier.wait(timeout=5)
            config = get_config(str(path))
            results.append(config)
        except Exception as e:  # pragma: no cover - failure path only
            errors.append(e)

    with patch.dict(os.environ, {}, clear=True):
        threads = [
            threading.Thread(target=worker, args=(config_files[i % len(config_files)],))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

    assert errors == []
    assert len(results) == 20
    # Every returned config must be internally consistent - api_key and
    # library_id from the *same* file, never a torn mix of two loads.
    for config in results:
        assert config.api_key is not None
        assert config.library_id is not None
        assert config.api_key.replace("key_", "") == config.library_id.replace("lib_", "")
