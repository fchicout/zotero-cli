import os
from pathlib import Path
from unittest.mock import patch

from zotero_cli.core.config import ConfigLoader


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
        "ZOTERO_LIBRARY_ID": "env_lib"
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

def test_precedence_env_over_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as f:
        f.write('[zotero]\napi_key = "file_key"\nuser_id = "file_user"\n')

    env = {
        "ZOTERO_API_KEY": "env_key"
    }

    with patch.dict(os.environ, env):
        loader = ConfigLoader(config_path=config_file)
        config = loader.load()
        assert config.api_key == "env_key" # Env wins
        assert config.user_id == "file_user" # File falls back

