"""Backups reuse the listing and don't recompress PDFs (Issues #426, #427)."""

import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock

from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.zotero_item import ZoteroItem


def _raw(key, item_type, parent=None, **data):
    raw = {"key": key, "version": 1, "data": {"key": key, "itemType": item_type, **data}}
    if parent:
        raw["data"]["parentItem"] = parent
    return raw


def _library():
    raws = [
        _raw("P1", "journalArticle", title="Paper"),
        _raw("A1", "attachment", "P1", linkMode="imported_file", filename="p.pdf",
             contentType="application/pdf"),
        _raw("S1", "attachment", "P1", linkMode="imported_file", filename="page.html",
             contentType="text/html"),
        _raw("N1", "note", "P1", note="<p>hi</p>"),
        _raw("P2", "book", title="Book"),
    ]
    return [ZoteroItem.from_raw_zotero_item(r) for r in raws]


def _gateway(items):
    gateway = MagicMock()
    gateway.get_all_items.return_value = iter(items)
    gateway.get_all_collections.return_value = []

    def download(key, path):
        with open(path, "wb") as f:
            f.write(b"%PDF-1.7 " + b"x" * 4000)
        return True

    gateway.download_attachment.side_effect = download
    return gateway


def test_library_backup_makes_no_children_or_item_requests():
    """~2.8 requests per item: children, then every child again."""
    gateway = _gateway(_library())
    out = BytesIO()
    BackupService(gateway).backup_system(out)

    gateway.get_item_children.assert_not_called()
    gateway.get_item.assert_not_called()
    with zipfile.ZipFile(out) as zf:
        data = json.loads(zf.read("data.json"))
    assert [d["key"] for d in data] == ["P1", "A1", "S1", "N1", "P2"]


def test_pdfs_are_stored_and_the_rest_is_deflated():
    out = BytesIO()
    BackupService(_gateway(_library())).backup_system(out)

    with zipfile.ZipFile(out) as zf:
        methods = {info.filename: info.compress_type for info in zf.infolist()}
        assert methods["attachments/P1/p.pdf"] == zipfile.ZIP_STORED
        assert methods["attachments/P1/page.html"] == zipfile.ZIP_DEFLATED
        assert methods["data.json"] == zipfile.ZIP_DEFLATED
        assert methods["manifest.json"] == zipfile.ZIP_DEFLATED
        assert zf.testzip() is None


def test_data_json_is_compact_and_complete():
    out = BytesIO()
    BackupService(_gateway(_library())).backup_system(out)

    with zipfile.ZipFile(out) as zf:
        text = zf.read("data.json").decode()
    assert "\n" not in text and ", " not in text
    assert len(json.loads(text)) == 5


def test_an_empty_library_writes_an_empty_array():
    out = BytesIO()
    BackupService(_gateway([])).backup_system(out)
    with zipfile.ZipFile(out) as zf:
        assert json.loads(zf.read("data.json")) == []


def test_new_archives_pass_verification(tmp_path):
    """Mixed STORED/DEFLATED entries and compact JSON still verify."""
    from zotero_cli.core.services.verify_service import VerifyService

    path = tmp_path / "library.zaf"
    BackupService(_gateway(_library())).backup_system(str(path))

    report = VerifyService().verify_archive(str(path))
    assert report.is_valid, report.errors
    assert report.item_count == 5
    assert report.file_count == 2
