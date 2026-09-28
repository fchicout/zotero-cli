"""Config errors say what was read and what to do (Issues #376, #397)."""

import os
from unittest.mock import patch

import pytest

from zotero_cli.core.config import ConfigLoader, ZoteroConfig, get_config, reset_config
from zotero_cli.core.exceptions import ConfigurationError
from zotero_cli.core.models import KeyIdentity
from zotero_cli.infra import repository_factory
from zotero_cli.infra.repository_factory import RepositoryFactory


@pytest.fixture(autouse=True)
def _clean():
    reset_config()
    repository_factory._IMPLICIT_TYPE.clear()
    with patch.dict(os.environ, {}, clear=False):
        for var in ("ZOTERO_API_KEY", "ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_TYPE", "ZOTERO_USER_ID"):
            os.environ.pop(var, None)
        yield
    reset_config()


def test_missing_config_path_fails(tmp_path):
    missing = tmp_path / "nope.toml"
    with pytest.raises(ConfigurationError, match="Config file not found") as raised:
        get_config(str(missing))
    assert str(missing) in str(raised.value)


def test_file_without_zotero_table_warns_once(tmp_path, capsys):
    path = tmp_path / "config.toml"
    path.write_text('api_key = "k"\nlibrary_id = "1"\n')
    ConfigLoader(path).load()
    ConfigLoader(path).load()
    err = capsys.readouterr().err
    assert err.count("has no [zotero] table") == 1


def test_missing_api_key_names_the_file_and_next_step(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[zotero]\nlibrary_id = "1"\n')
    config = get_config(str(path))
    with pytest.raises(ConfigurationError) as raised:
        RepositoryFactory.get_zotero_gateway(config, offline=False)
    msg = str(raised.value)
    assert "No Zotero API key" in msg
    assert str(path) in msg
    assert "zotero-cli init" in msg and "ZOTERO_API_KEY" in msg


def test_missing_library_names_the_settings():
    config = ZoteroConfig(api_key="k")
    with pytest.raises(ConfigurationError) as raised:
        RepositoryFactory.get_zotero_gateway(config, offline=False)
    assert "library_id" in str(raised.value) and "ZOTERO_LIBRARY_ID" in str(raised.value)


def test_offline_without_database_path_says_where_it_usually_is():
    with pytest.raises(ConfigurationError) as raised:
        RepositoryFactory.get_zotero_gateway(ZoteroConfig(api_key="k"), offline=True)
    assert "database_path" in str(raised.value)
    assert "zotero.sqlite" in str(raised.value)


def test_library_type_set_tracks_whether_it_was_given(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[zotero]\napi_key = "k"\nlibrary_id = "1"\n')
    assert ConfigLoader(path).load().library_type_set is False
    with patch.dict(os.environ, {"ZOTERO_LIBRARY_TYPE": "group"}):
        assert ConfigLoader(path).load().library_type_set is True


def _implicit(library_id="1234567"):
    return ZoteroConfig(api_key="k", library_id=library_id, library_type_set=False)


def test_implicit_type_is_user_for_the_keys_own_library():
    """Issue #397: the tutorial puts the userID in ZOTERO_LIBRARY_ID."""
    with patch.object(
        repository_factory.ZoteroAPIClient,
        "resolve_key_identity",
        return_value=KeyIdentity(user_id=1234567, username="u", access={}),
    ) as probe:
        assert RepositoryFactory.resolve_target(_implicit()) == ("1234567", "user")
        RepositoryFactory.resolve_target(_implicit())
    probe.assert_called_once()  # cached per process


def test_implicit_type_stays_group_for_another_id():
    with patch.object(
        repository_factory.ZoteroAPIClient,
        "resolve_key_identity",
        return_value=KeyIdentity(user_id=42, username="u", access={}),
    ):
        assert RepositoryFactory.resolve_target(_implicit("999")) == ("999", "group")


def test_implicit_type_falls_back_to_group_when_the_probe_fails():
    with patch.object(
        repository_factory.ZoteroAPIClient, "resolve_key_identity", side_effect=OSError("down")
    ):
        assert RepositoryFactory.resolve_target(_implicit()) == ("1234567", "group")


def test_explicit_type_is_never_probed():
    config = ZoteroConfig(api_key="k", library_id="1234567", library_type="group")
    with patch.object(repository_factory.ZoteroAPIClient, "resolve_key_identity") as probe:
        assert RepositoryFactory.resolve_target(config) == ("1234567", "group")
    probe.assert_not_called()
