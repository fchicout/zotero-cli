"""An unwritable storage directory is one clear error (Issue #419)."""

from unittest.mock import patch

import pytest

from zotero_cli.core import config as config_module
from zotero_cli.core import logging_config
from zotero_cli.core.exceptions import ConfigurationError


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("ZOTERO_CLI_CONTAINER", raising=False)
    config_module.reset_config()
    yield tmp_path / "zotero-cli"
    config_module.reset_config()


def _eperm(*_args, **_kwargs):
    raise PermissionError(1, "Operation not permitted")


def test_state_dir_not_ours_is_one_error_naming_it(storage):
    with patch.object(config_module, "make_private_dir", side_effect=_eperm):
        with pytest.raises(ConfigurationError) as raised:
            config_module.get_state_dir()
    msg = str(raised.value)
    assert str(storage) in msg
    assert "Operation not permitted" in msg
    assert "XDG_CONFIG_HOME" in msg


def test_state_dir_in_the_container_explains_the_mount(storage, monkeypatch):
    monkeypatch.setenv("ZOTERO_CLI_CONTAINER", "1")
    with patch.object(config_module, "make_private_dir", side_effect=_eperm):
        with pytest.raises(ConfigurationError, match="/config/zotero-cli") as raised:
            config_module.get_state_dir()
    assert "--user" in str(raised.value)


def test_state_dir_without_write_access_is_reported(storage):
    with patch.object(config_module.os, "access", return_value=False):
        with pytest.raises(ConfigurationError, match="permission denied"):
            config_module.get_state_dir()


def test_log_setup_failure_names_the_directory(storage, capsys):
    """It said "Could not set up log file at None"."""
    logging_config.reset_logging_for_tests()
    try:
        with patch.object(logging_config, "_make_private_dir", side_effect=_eperm):
            logging_config.setup_logging()
    finally:
        logging_config.reset_logging_for_tests()
    err = capsys.readouterr().err
    assert "at None" not in err
    assert str(storage / "logs") in err
