"""GHSA-4ffp-8wvr-hmvg: with --config elsewhere, state (job queue, vector
stores, discovery graphs) was written world-readable next to the config
file, often a shared project folder or a git repository. It now lives in a
private profile inside the per-user zotero-cli directory."""

import os
import stat
from pathlib import Path

import pytest

from zotero_cli.core import config as cfg


@pytest.fixture(autouse=True)
def _fresh_config():
    cfg.reset_config()
    yield
    cfg.reset_config()


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_default_config_keeps_state_in_the_default_dir():
    cfg.get_config()
    assert cfg.get_storage_dir() == cfg.default_storage_dir()


def test_custom_config_state_goes_to_a_private_profile(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "zc.toml").write_text("[zotero]\n")
    cfg.get_config(str(project / "zc.toml"))

    state = cfg.get_state_dir()

    assert state.parent == cfg.default_storage_dir() / "profiles"
    assert project not in state.parents
    if os.name != "nt":
        assert _mode(state) == 0o700


def test_two_configs_get_different_profiles(tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "config.toml").write_text("[zotero]\n")
    cfg.get_config(str(tmp_path / "a" / "config.toml"))
    first = cfg.get_storage_dir()
    cfg.get_config(str(tmp_path / "b" / "config.toml"))
    assert cfg.get_storage_dir() != first


def test_state_left_next_to_the_config_moves_into_the_profile(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    (project / "zc.toml").write_text("[zotero]\n")
    (project / "jobs.sqlite").write_text("jobs")
    (project / "vector_store_123.sqlite").write_text("vectors")
    (project / "discovery_graph_123.json").write_text("{}")
    (project / "notes.txt").write_text("not ours")
    cfg.get_config(str(project / "zc.toml"))

    state = cfg.get_state_dir()

    for name in ("jobs.sqlite", "vector_store_123.sqlite", "discovery_graph_123.json"):
        assert not (project / name).exists()
        assert (state / name).exists()
        if os.name != "nt":
            assert _mode(state / name) == 0o600
    assert (project / "notes.txt").exists()
    assert "moved" in capsys.readouterr().err


def test_migration_never_overwrites_existing_state(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "zc.toml").write_text("[zotero]\n")
    cfg.get_config(str(project / "zc.toml"))
    state = cfg.get_state_dir()
    (state / "jobs.sqlite").write_text("current")
    (project / "jobs.sqlite").write_text("stale")

    cfg.get_state_dir()

    assert (state / "jobs.sqlite").read_text() == "current"
    assert (project / "jobs.sqlite").read_text() == "stale"


def test_job_queue_uses_the_private_state_dir(tmp_path):
    from zotero_cli.infra.service_factory import ServiceFactory

    project = tmp_path / "project"
    project.mkdir()
    (project / "zc.toml").write_text("[zotero]\n")
    cfg.get_config(str(project / "zc.toml"))

    ServiceFactory.get_job_queue_service()

    assert not (project / "jobs.sqlite").exists()
    assert (cfg.get_storage_dir() / "jobs.sqlite").exists()
