"""Issue #400: the e2e suite writes to a real Zotero library, so it must
never run from a bare `pytest` or without naming the library it may touch."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import tomllib

from tests.e2e.conftest import e2e_skip_reason

ROOT = Path(__file__).resolve().parents[2]


def test_bare_pytest_does_not_collect_e2e():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    testpaths = config["tool"]["pytest"]["ini_options"]["testpaths"]
    assert all(not p.startswith("tests/e2e") and p != "tests" for p in testpaths)


def _config_for(library_id: str) -> MagicMock:
    config = MagicMock()
    config.resolve_library_target.return_value = (library_id, "user")
    return config


@pytest.mark.parametrize(
    "env, configured, allowed",
    [
        ({}, "111", False),
        ({"ZOTERO_CLI_E2E": "1"}, "111", False),
        ({"ZOTERO_CLI_E2E": "true", "ZOTERO_CLI_E2E_LIBRARY_ID": "111"}, "111", False),
        ({"ZOTERO_CLI_E2E": "1", "ZOTERO_CLI_E2E_LIBRARY_ID": "222"}, "111", False),
        ({"ZOTERO_CLI_E2E": "1", "ZOTERO_CLI_E2E_LIBRARY_ID": "111"}, "111", True),
    ],
)
def test_e2e_runs_only_opted_in_against_the_named_library(monkeypatch, env, configured, allowed):
    monkeypatch.delenv("ZOTERO_CLI_E2E", raising=False)
    monkeypatch.delenv("ZOTERO_CLI_E2E_LIBRARY_ID", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with patch("zotero_cli.core.config.get_config", return_value=_config_for(configured)):
        assert (e2e_skip_reason() is None) is allowed


def test_e2e_refuses_when_the_library_cannot_be_resolved(monkeypatch):
    monkeypatch.setenv("ZOTERO_CLI_E2E", "1")
    monkeypatch.setenv("ZOTERO_CLI_E2E_LIBRARY_ID", "111")
    with patch("zotero_cli.core.config.get_config", side_effect=RuntimeError("no config")):
        assert "could not resolve" in (e2e_skip_reason() or "")
