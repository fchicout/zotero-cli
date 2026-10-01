"""Packaging metadata stays consistent (Issue #415)."""

import tomllib
from pathlib import Path

import zotero_cli

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_and_package_versions_agree():
    """The version lives in two places; the release bumps both."""
    assert PYPROJECT["project"]["version"] == zotero_cli.VERSION == zotero_cli.__version__


def test_license_uses_spdx_metadata_not_deprecated_forms():
    """setuptools drops the licence table and classifiers on 2027-02-18."""
    project = PYPROJECT["project"]
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert not any(c.startswith("License ::") for c in project["classifiers"])
    assert any(r.startswith("setuptools>=77") for r in PYPROJECT["build-system"]["requires"])
