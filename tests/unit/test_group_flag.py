"""Issue #661: `--group` names the group library of one run."""

import sqlite3
from pathlib import Path
from typing import Iterator

import pytest

from zotero_cli.cli.main import build_parser
from zotero_cli.core.config import (
    ZoteroConfig,
    get_config,
    parse_group_id,
    set_group_override,
)
from zotero_cli.infra.factory import GatewayFactory


@pytest.fixture(autouse=True)
def _no_group_override() -> Iterator[None]:
    set_group_override(None)
    yield
    set_group_override(None)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("6629576", "6629576"),
        ("  777  ", "777"),
        ("https://www.zotero.org/groups/6629576", "6629576"),
        ("https://www.zotero.org/groups/6629576/lab-group/library", "6629576"),
        ("zotero.org/groups/12", "12"),
    ],
)
def test_a_group_is_given_as_its_id_or_its_url(given: str, expected: str) -> None:
    assert parse_group_id(given) == expected


@pytest.mark.parametrize(
    "given",
    ["", "abc", "0", "-5", "12abc", "https://www.zotero.org/users/42", "https://example.org/"],
)
def test_anything_else_is_not_a_group(given: str) -> None:
    with pytest.raises(ValueError, match="not a group"):
        parse_group_id(given)


def test_the_flag_is_listed_in_the_help() -> None:
    help_text = build_parser().format_help()

    assert "--group GROUP" in help_text
    assert "--user" in help_text


def _write_config(tmp_path: Path, library_type: str, library_id: str) -> str:
    path = tmp_path / "config.toml"
    path.write_text(
        f'[zotero]\napi_key = "key"\nuser_id = "42"\n'
        f'library_id = "{library_id}"\nlibrary_type = "{library_type}"\n'
    )
    return str(path)


def test_the_override_beats_the_configured_library(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, "user", "42")

    set_group_override("777")
    config = get_config(config_path)

    assert (config.library_id, config.library_type, config.library_type_set) == (
        "777",
        "group",
        True,
    )
    assert config.resolve_library_target() == ("777", "group")
    assert config.resolve_scoping_id() == "777"


def test_without_the_override_the_configuration_is_used(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, "user", "42")

    set_group_override("777")
    get_config(config_path)
    set_group_override(None)
    config = get_config(config_path)

    assert (config.library_id, config.library_type) == ("42", "user")


def test_the_override_beats_the_environment_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "42")
    monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "user")

    set_group_override("777")
    config = get_config(_write_config(tmp_path, "user", "42"))

    assert config.resolve_library_target() == ("777", "group")


def test_the_offline_gateway_reads_the_chosen_library(tmp_path: Path) -> None:
    database = tmp_path / "zotero.sqlite"
    sqlite3.connect(database).close()
    config = ZoteroConfig(
        api_key="key",
        library_id="42",
        library_type="user",
        user_id="42",
        database_path=str(database),
    )

    plain = GatewayFactory.get_zotero_gateway(config, offline=True)
    set_group_override("777")
    chosen = get_config(_write_config(tmp_path, "user", "42"))
    config_for_group = ZoteroConfig(
        api_key="key",
        library_id=chosen.library_id,
        library_type=chosen.library_type,
        user_id="42",
        database_path=str(database),
    )
    gateway = GatewayFactory.get_zotero_gateway(config_for_group, offline=True)

    assert getattr(plain, "library_id", None) == "42"
    assert getattr(gateway, "library_id", None) == "777"
    assert getattr(gateway, "library_type", None) == "group"
