"""Issue #455: readers accept every older format version and refuse a newer
major one (docs/COMPATIBILITY.md), instead of misreading it."""

import io
import json
import zipfile

import pytest

from zotero_cli.core.exceptions import DataFileError
from zotero_cli.core.utils.format_version import check_format_version


@pytest.mark.parametrize("version", [None, "1.0", "1.2", "1.9", 1, "0.5"])
def test_current_and_older_versions_are_accepted(version):
    check_format_version("backup archive", version, "x")


@pytest.mark.parametrize("version", ["2.0", "2", 3, "10.1"])
def test_a_newer_major_is_refused(version):
    with pytest.raises(DataFileError, match="newer zotero-cli"):
        check_format_version("backup archive", version, "x")


def test_a_non_version_is_refused():
    with pytest.raises(DataFileError, match="unrecognised"):
        check_format_version("backup archive", "banana", "x")


def _zaf(tmp_path, manifest) -> str:
    path = tmp_path / "backup.zaf"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("data.json", "[]")
    path.write_bytes(buffer.getvalue())
    return str(path)


def _restore(path):
    from unittest.mock import MagicMock

    from zotero_cli.core.services.restore_service import RestoreService

    return RestoreService(MagicMock()).restore_archive(path, dry_run=True)


def test_restore_refuses_a_newer_archive(tmp_path):
    report = _restore(_zaf(tmp_path, {"format": "zaf", "version": "2.0"}))
    assert any("newer zotero-cli" in e for e in report.errors)


def test_restore_refuses_a_non_zaf_manifest(tmp_path):
    report = _restore(_zaf(tmp_path, {"format": "something-else", "version": "1.0"}))
    assert any("not a zotero-cli backup archive" in e for e in report.errors)


def test_restore_accepts_the_current_archive(tmp_path):
    report = _restore(_zaf(tmp_path, {"format": "zaf", "version": "1.1"}))
    assert report.errors == []


def test_verify_flags_a_newer_archive(tmp_path):
    from zotero_cli.core.services.verify_service import VerifyService

    report = VerifyService().verify_archive(_zaf(tmp_path, {"format": "zaf", "version": "2.0"}))
    assert not report.is_valid
    assert any("newer zotero-cli" in e for e in report.errors)
