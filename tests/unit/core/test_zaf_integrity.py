import io
import json
import os
import zipfile
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.restore_service import RestoreReport, RestoreService
from zotero_cli.core.services.verify_service import VerifyService


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def dummy_zaf():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        manifest = {
            "scope_type": "collection",
            "timestamp": "2024-01-01",
            "file_map": {
                "ATT1": {
                    "path": "attachments/P1/file.pdf",
                    "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                }  # empty file hash
            },
        }
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr(
            "data.json",
            json.dumps(
                [
                    {"key": "P1", "data": {"itemType": "journalArticle", "title": "Test"}},
                    {
                        "key": "ATT1",
                        "data": {
                            "itemType": "attachment",
                            "parentItem": "P1",
                            "linkMode": "imported_file",
                        },
                    },
                ]
            ),
        )
        zf.writestr("attachments/P1/file.pdf", b"")
    buffer.seek(0)
    return buffer


def test_verify_service_success(dummy_zaf, tmp_path):
    zaf_path = tmp_path / "test.zaf"
    zaf_path.write_bytes(dummy_zaf.getvalue())

    service = VerifyService()
    report = service.verify_archive(str(zaf_path))

    assert report.is_valid is True
    assert report.item_count == 2
    assert report.file_count == 1


def test_verify_service_library_scope_success(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        manifest = {"scope_type": "library"}
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("data.json", "[]")
        zf.writestr("collections.json", "[]")
    zaf_path = tmp_path / "lib.zaf"
    zaf_path.write_bytes(buffer.getvalue())

    service = VerifyService()
    report = service.verify_archive(str(zaf_path))
    assert report.is_valid is True
    assert report.collection_count == 0


def test_verify_service_checksum_failure(dummy_zaf, tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        manifest = {"file_map": {"ATT1": {"path": "file.pdf", "checksum": "wrong"}}}
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("data.json", "[]")
        zf.writestr("file.pdf", b"tampered")

    zaf_path = tmp_path / "bad.zaf"
    zaf_path.write_bytes(buffer.getvalue())

    service = VerifyService()
    report = service.verify_archive(str(zaf_path))
    assert report.is_valid is False
    assert any("Checksum mismatch" in e for e in report.errors)


def test_verify_service_missing_files(tmp_path):
    zaf_path = tmp_path / "not_a_zip.zaf"
    zaf_path.write_text("hello")

    service = VerifyService()
    report = service.verify_archive(str(zaf_path))
    assert report.is_valid is False

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("data.json", "[]")
    zaf_path = tmp_path / "missing_manifest.zaf"
    zaf_path.write_bytes(buffer.getvalue())
    report = service.verify_archive(str(zaf_path))
    assert "Missing manifest.json" in report.errors


def _restore_service(gateway):
    return RestoreService(gateway, gateway, gateway, gateway)


def test_restore_service_dry_run(dummy_zaf, tmp_path):
    zaf_path = tmp_path / "restore.zaf"
    zaf_path.write_bytes(dummy_zaf.getvalue())

    mock_gw = MagicMock()
    mock_gw.get_all_collections.return_value = []
    mock_gw.get_all_items.return_value = []

    service = _restore_service(mock_gw)
    report = service.restore_archive(str(zaf_path), dry_run=True)

    assert report.is_dry_run is True
    assert report.items_created == 1
    assert report.attachments_uploaded == 1


def test_restore_collections_hierarchy(mock_gateway):
    service = _restore_service(mock_gateway)

    colls = [
        {"key": "C1", "data": {"name": "Root", "parentCollection": None}},
        {"key": "C2", "data": {"name": "Child", "parentCollection": "C1"}},
    ]
    mock_gateway.get_all_collections.return_value = []
    mock_gateway.create_collection.side_effect = ["NEW1", "NEW2"]

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport(is_dry_run=False)
    service._restore_collections(colls, report)

    assert service.coll_map["C1"] == "NEW1"
    assert service.coll_map["C2"] == "NEW2"


def test_restore_child_parent_not_found(mock_gateway):
    service = _restore_service(mock_gateway)
    # Child with parent that is not in map
    child_raw = {"key": "ATT1", "data": {"itemType": "attachment", "parentItem": "MISSING"}}

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport()
    # Should return early and not crash
    service._restore_child_item(child_raw, MagicMock(), {}, report)
    assert not mock_gateway.upload_attachment_item.called


def test_restore_service_idempotency_none(mock_gateway):
    service = _restore_service(mock_gateway)
    # Data with no DOI or Title
    data = {"itemType": "journalArticle"}
    result = service._find_existing_item(data, {}, {})
    assert result is None


def test_restore_attachment_mode_mismatch(dummy_zaf, tmp_path, mock_gateway):
    zaf_path = tmp_path / "mode.zaf"
    zaf_path.write_bytes(dummy_zaf.getvalue())
    service = _restore_service(mock_gateway)
    # web_page or similar mode that we don't upload
    child_raw = {"key": "ATT1", "data": {"itemType": "attachment", "linkMode": "linked_url"}}

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport()
    with zipfile.ZipFile(zaf_path, "r") as zf:
        service._restore_attachment(child_raw, zf, {}, "PARENT", report)
    assert not mock_gateway.upload_attachment_item.called


def test_restore_item_creation_failure(mock_gateway):
    from zotero_cli.core.services.restore_service import RestoreReport

    service = _restore_service(mock_gateway)
    item_raw = {"key": "K1", "data": {"itemType": "journalArticle", "title": "Fail"}}
    mock_gateway.create_generic_item.return_value = None

    report = RestoreReport()
    service._restore_single_item(item_raw, MagicMock(), {}, report, {}, {})

    assert report.items_created == 0
    assert len(report.errors) == 1
    assert "Failed to create item" in report.errors[0]


def test_verify_service_calculate_checksum_error(tmp_path):
    service = VerifyService()
    # Mock zipfile.ZipFile object that fails on open, simulating the kind of
    # error zf.open() actually raises for a corrupt/unreadable entry.
    mock_zf = MagicMock()
    mock_zf.open.side_effect = zipfile.BadZipFile("File read error")

    with pytest.raises(zipfile.BadZipFile):
        service._calculate_checksum(mock_zf, "any_path")


def test_restore_collections_match_existing(mock_gateway):
    service = _restore_service(mock_gateway)
    colls = [{"key": "C1", "data": {"name": "Existing", "parentCollection": None}}]
    # Mock existing match
    mock_gateway.get_all_collections.return_value = [
        {"key": "NEW_KEY", "data": {"name": "Existing", "parentCollection": None}}
    ]

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport(is_dry_run=False)
    service._restore_collections(colls, report)

    assert service.coll_map["C1"] == "NEW_KEY"
    assert report.collections_created == 0


def test_restore_note_creation(mock_gateway):
    service = _restore_service(mock_gateway)
    item_key = "K1"
    note_data = {"note": "New note"}
    # Mock no existing notes
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_generic_item.return_value = "NEWNOTE"

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport(is_dry_run=False)
    service._restore_note(note_data, item_key, report)

    mock_gateway.create_generic_item.assert_called_once_with(
        {"itemType": "note", "note": "New note", "tags": [], "parentItem": item_key}
    )


def test_verify_service_legacy_manifest(tmp_path):
    # Test file_map with string values (legacy)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        manifest = {"file_map": {"ATT1": "attachments/P1/file.pdf"}}
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("data.json", "[]")
        zf.writestr("attachments/P1/file.pdf", b"data")

    zaf_path = tmp_path / "legacy.zaf"
    zaf_path.write_bytes(buffer.getvalue())

    service = VerifyService()
    report = service.verify_archive(str(zaf_path))
    assert report.is_valid is True
    assert report.file_count == 1


def test_verify_service_library_scope_missing_collections_file(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        manifest = {"scope_type": "library"}
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("data.json", "[]")

    zaf_path = tmp_path / "missing_colls.zaf"
    zaf_path.write_bytes(buffer.getvalue())

    service = VerifyService()
    report = service.verify_archive(str(zaf_path))
    assert report.is_valid is False
    assert any("Missing collections.json" in e for e in report.errors)


def test_restore_service_idempotency_doi_none(mock_gateway):
    service = _restore_service(mock_gateway)

    data = {"DOI": "10.1/none", "title": "No Match"}
    result = service._find_existing_item(data, {}, {})
    assert result is None


def test_verify_service_missing_path_in_manifest(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        manifest = {
            "file_map": {"ATT1": {"checksum": "somehash"}}  # Missing 'path'
        }
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("data.json", "[]")

    zaf_path = tmp_path / "nopath.zaf"
    zaf_path.write_bytes(buffer.getvalue())

    service = VerifyService()
    report = service.verify_archive(str(zaf_path))
    assert report.is_valid is False
    assert any("Missing path in manifest" in e for e in report.errors)


def test_restore_collections_failure(mock_gateway):
    service = _restore_service(mock_gateway)
    colls = [{"key": "C1", "data": {"name": "Fail", "parentCollection": None}}]
    mock_gateway.get_all_collections.return_value = []
    # Mock creation failure
    mock_gateway.create_collection.return_value = None

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport(is_dry_run=False)
    service._restore_collections(colls, report)

    assert len(report.errors) == 1
    assert "Failed to create collection" in report.errors[0]


def test_restore_collections_fetches_existing_once_for_many_collections(mock_gateway):
    """Regression test for Issue #277: _restore_collections must call
    get_all_collections() once for the whole batch, not once per
    collection being restored."""
    service = _restore_service(mock_gateway)
    colls = [
        {"key": "C1", "data": {"name": "One", "parentCollection": None}},
        {"key": "C2", "data": {"name": "Two", "parentCollection": None}},
        {"key": "C3", "data": {"name": "Three", "parentCollection": None}},
    ]
    mock_gateway.get_all_collections.return_value = []
    mock_gateway.create_collection.side_effect = ["N1", "N2", "N3"]

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport(is_dry_run=False)
    service._restore_collections(colls, report)

    mock_gateway.get_all_collections.assert_called_once()
    assert report.collections_created == 3


def test_build_existing_item_indexes_single_scan(mock_gateway):
    """Regression test for Issue #277: the DOI/title indexes must come from
    one get_all_items() pass, and _find_existing_item must consult those
    indexes rather than re-scanning the library per item."""
    from zotero_cli.core.zotero_item import ZoteroItem

    item1 = ZoteroItem(
        key="P1", version=1, item_type="journalArticle", doi="10.1/ABC", title="Paper One"
    )
    item2 = ZoteroItem(key="P2", version=1, item_type="journalArticle", title="Paper Two")
    mock_gateway.get_all_items.return_value = [item1, item2]

    service = _restore_service(mock_gateway)
    doi_index, title_index = service._build_existing_item_indexes()

    mock_gateway.get_all_items.assert_called_once()
    assert doi_index["10.1/abc"] == [item1]
    assert title_index["paper two"] == [item2]

    # DOI match (case/prefix-insensitive via normalize_doi)
    match = service._find_existing_item({"DOI": "https://doi.org/10.1/ABC"}, doi_index, title_index)
    assert match is item1

    # Title fallback when DOI doesn't match anything indexed
    match = service._find_existing_item(
        {"DOI": "10.9/unrelated", "title": "Paper Two"}, doi_index, title_index
    )
    assert match is item2

    mock_gateway.get_all_items.assert_called_once()  # still only the one scan
    mock_gateway.get_items_by_doi.assert_not_called()


def test_restore_archive_builds_indexes_once_for_multiple_items(dummy_zaf, tmp_path):
    """Regression test for Issue #277: restore_archive must build the
    DOI/title index once up front and reuse it, not per item."""
    zaf_path = tmp_path / "multi.zaf"
    with zipfile.ZipFile(zaf_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"file_map": {}}))
        zf.writestr(
            "data.json",
            json.dumps(
                [
                    {"key": "P1", "data": {"itemType": "journalArticle", "title": "A"}},
                    {"key": "P2", "data": {"itemType": "journalArticle", "title": "B"}},
                    {"key": "P3", "data": {"itemType": "journalArticle", "title": "C"}},
                ]
            ),
        )

    mock_gw = MagicMock()
    mock_gw.get_all_items.return_value = []
    mock_gw.create_generic_item.side_effect = ["N1", "N2", "N3"]

    service = _restore_service(mock_gw)
    report = service.restore_archive(str(zaf_path), dry_run=False)

    mock_gw.get_all_items.assert_called_once()
    mock_gw.get_items_by_doi.assert_not_called()
    assert report.items_created == 3


def _zaf_with_attachment(tmp_path, payload: bytes):
    path = tmp_path / "a.zaf"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_LZMA) as zf:
        zf.writestr("files/ATT1/paper.pdf", payload)
    return zipfile.ZipFile(path)


def test_restore_attachment_over_the_size_limit_is_refused_and_leaves_no_temp_file(
    tmp_path, monkeypatch
):
    """A crafted .zaf whose attachment expands past the limit must not be
    written out in full, and its temp file must not be left behind."""
    import tempfile as tempfile_mod

    from zotero_cli.core.services import restore_service as rs

    monkeypatch.setattr(rs, "MAX_ATTACHMENT_BYTES", 1024)
    created = []
    real_ntf = tempfile_mod.NamedTemporaryFile

    def tracking_ntf(*args, **kwargs):
        handle = real_ntf(*args, **kwargs)
        created.append(handle.name)
        return handle

    monkeypatch.setattr(tempfile_mod, "NamedTemporaryFile", tracking_ntf)

    gateway = MagicMock()
    service = _restore_service(gateway)
    report = rs.RestoreReport()
    zf = _zaf_with_attachment(tmp_path, b"%PDF-1.7" + b"\0" * 100_000)
    manifest = {"file_map": {"ATT1": {"path": "files/ATT1/paper.pdf"}}}

    service._restore_attachment(
        {"key": "ATT1", "data": {"linkMode": "imported_file"}}, zf, manifest, "NEWPARENT", report
    )

    gateway.upload_attachment_item.assert_not_called()
    assert report.errors
    assert "limit" in report.errors[0]
    assert created
    assert not any(os.path.exists(p) for p in created)


def test_restore_refuses_oversized_data_json(tmp_path, monkeypatch):
    from zotero_cli.core.utils import archive_safety

    monkeypatch.setattr(archive_safety.read_json_member, "__defaults__", (1024,))
    path = tmp_path / "big.zaf"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_LZMA) as zf:
        zf.writestr("manifest.json", "{}")
        zf.writestr("data.json", "[" + " " * 100_000 + "]")

    report = _restore_service(MagicMock()).restore_archive(str(path))
    assert report.errors
    assert "limit" in report.errors[0]


def test_restore_notes_ask_for_each_parent_s_children_once(mock_gateway):
    """Issue #440: one children request per restored note."""
    service = _restore_service(mock_gateway)
    report = RestoreReport()
    mock_gateway.get_item_children.return_value = [
        {"key": "N0", "data": {"itemType": "note", "note": "already there"}}
    ]
    mock_gateway.create_generic_item.return_value = "NEWNOTE"

    for text in ("already there", "first", "second", "first"):
        service._restore_note({"note": text}, "PARENT", report)

    mock_gateway.get_item_children.assert_called_once_with("PARENT")
    created = [c.args[0]["note"] for c in mock_gateway.create_generic_item.call_args_list]
    assert created == ["first", "second"]  # no duplicates, nothing twice


def test_restore_notes_on_a_new_parent_make_no_children_request(mock_gateway):
    service = _restore_service(mock_gateway)
    report = RestoreReport()
    mock_gateway.create_generic_item.return_value = "NEWKEY"
    service._restore_single_item(
        {"key": "OLD", "data": {"itemType": "journalArticle", "title": "A new paper"}},
        MagicMock(),
        {},
        report,
        {},
        {},
    )

    service._restore_note({"note": "hello"}, "NEWKEY", report)

    mock_gateway.get_item_children.assert_not_called()
    mock_gateway.create_generic_item.assert_called_with(
        {"itemType": "note", "note": "hello", "tags": [], "parentItem": "NEWKEY"}
    )


@pytest.mark.parametrize(
    ("link_mode", "content_type", "expected_mime"),
    [
        ("imported_file", None, "application/pdf"),
        ("imported_url", "text/html", "text/html"),
        ("imported_url", "application/pdf", "application/pdf"),
        ("imported_file", "image/png", "image/png"),
    ],
)
def test_restore_uploads_every_stored_attachment_with_its_own_content_type(
    tmp_path, link_mode, content_type, expected_mime
):
    """Issue #655: web snapshots and connector-downloaded PDFs are `imported_url`; the upload
    used to be refused for them and assumed a PDF for everything else."""
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway
    from zotero_cli.core.services import restore_service as rs

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.upload_attachment_item.return_value = "NEWATT"
    service = _restore_service(gateway)
    report = rs.RestoreReport()
    zf = _zaf_with_attachment(tmp_path, b"stored bytes")
    manifest = {"file_map": {"ATT1": {"path": "files/ATT1/paper.pdf"}}}
    data = {"linkMode": link_mode}
    if content_type:
        data["contentType"] = content_type

    service._restore_attachment({"key": "ATT1", "data": data}, zf, manifest, "NEWPARENT", report)

    gateway.upload_attachment_item.assert_called_once()
    assert gateway.upload_attachment_item.call_args.args[0] == "NEWPARENT"
    assert gateway.upload_attachment_item.call_args.kwargs["mime_type"] == expected_mime
    assert report.attachments_uploaded == 1


@pytest.mark.parametrize("no_parent", [False, None, ""])
def test_a_root_collection_matches_however_the_api_says_it_has_no_parent(no_parent):
    """Issue #680: the Web API answers `false`; the restore compared that with None."""
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_collections.return_value = [
        {"key": "EXIST1", "data": {"name": "Reviews", "parentCollection": no_parent}}
    ]
    service = _restore_service(gateway)
    report = RestoreReport()

    service._restore_collections(
        [{"key": "C1", "data": {"name": "Reviews", "parentCollection": False}}], report
    )

    assert service.coll_map["C1"] == "EXIST1"
    assert report.collections_created == 0
    gateway.create_collection.assert_not_called()


@pytest.mark.parametrize(
    ("existing", "uploads"),
    [
        ([{"md5": "a2d7ae0f6e9b8a0f5f5b4b4d1b3f4f0a", "filename": "other.pdf"}], 1),  # other file
        ([{"filename": "paper.pdf"}], 0),  # no md5: the file name decides
        ([{"filename": "other.pdf"}], 1),
        ([], 1),
    ],
    ids=["different-md5", "same-name-without-md5", "other-name-without-md5", "none"],
)
def test_an_attachment_of_an_existing_item_is_uploaded_unless_it_is_there(
    tmp_path, existing, uploads
):
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.upload_attachment_item.return_value = "NEWATT"
    gateway.get_item_children.return_value = [
        {"data": {"itemType": "attachment", **fields}} for fields in existing
    ]
    service = _restore_service(gateway)
    report = RestoreReport()
    zf = _zaf_with_attachment(tmp_path, b"%PDF-1.7 content")
    manifest = {"file_map": {"ATT1": {"path": "files/ATT1/paper.pdf"}}}
    raw = {"key": "ATT1", "data": {"linkMode": "imported_file", "filename": "paper.pdf"}}

    service._restore_attachment(raw, zf, manifest, "EXISTING1", report)

    assert gateway.upload_attachment_item.call_count == uploads
    assert report.attachments_skipped_existing == 1 - uploads


def test_an_attachment_with_the_same_md5_is_not_uploaded_again(tmp_path):
    import hashlib
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    payload = b"%PDF-1.7 the same bytes"
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_item_children.return_value = [
        {
            "data": {
                "itemType": "attachment",
                "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
                "filename": "renamed-by-someone.pdf",
            }
        }
    ]
    service = _restore_service(gateway)
    report = RestoreReport()
    zf = _zaf_with_attachment(tmp_path, payload)
    manifest = {"file_map": {"ATT1": {"path": "files/ATT1/paper.pdf"}}}

    service._restore_attachment(
        {"key": "ATT1", "data": {"linkMode": "imported_file", "filename": "paper.pdf"}},
        zf,
        manifest,
        "EXISTING1",
        report,
    )

    gateway.upload_attachment_item.assert_not_called()
    assert report.attachments_skipped_existing == 1
    assert report.attachments_uploaded == 0


def test_an_item_created_by_this_run_is_not_asked_for_its_attachments(tmp_path):
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.upload_attachment_item.return_value = "NEWATT"
    service = _restore_service(gateway)
    service._created.add("NEWITEM1")
    zf = _zaf_with_attachment(tmp_path, b"%PDF-1.7 x")
    manifest = {"file_map": {"ATT1": {"path": "files/ATT1/paper.pdf"}}}

    service._restore_attachment(
        {"key": "ATT1", "data": {"linkMode": "imported_file"}},
        zf,
        manifest,
        "NEWITEM1",
        RestoreReport(),
    )

    gateway.get_item_children.assert_not_called()
    gateway.upload_attachment_item.assert_called_once()


def test_a_note_is_created_with_its_tags_and_their_types():
    """Issue #682: the text was all that was sent."""
    from zotero_cli.core.services.restore_service import _note_payload

    data = {"note": "<p>x</p>", "tags": [{"tag": "a", "type": 0}, {"tag": "b", "type": 1}]}

    payload = _note_payload(data, parent="NEWPARENT")

    assert payload == {
        "itemType": "note",
        "note": "<p>x</p>",
        "tags": [{"tag": "a", "type": 0}, {"tag": "b", "type": 1}],
        "parentItem": "NEWPARENT",
    }


def test_a_note_without_tags_is_created_with_an_empty_tag_list():
    from zotero_cli.core.services.restore_service import _note_payload

    payload = _note_payload({"note": "<p>x</p>"}, collections=["COL1"])

    assert payload == {"itemType": "note", "note": "<p>x</p>", "tags": [], "collections": ["COL1"]}


def test_a_trashed_note_is_created_with_the_deleted_flag():
    """Issue #683: the real API honours `deleted` on create."""
    from zotero_cli.core.services.restore_service import _note_payload

    payload = _note_payload({"note": "<p>x</p>", "deleted": 1}, parent="NEWPARENT")

    assert payload["deleted"] == 1
    assert "deleted" not in _note_payload({"note": "<p>x</p>"}, parent="NEWPARENT")


def _service_with(gateway, trash, children=()):
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_items.return_value = iter([])
    gateway.get_trash_items.return_value = iter(trash)
    gateway.get_item_children.return_value = list(children)
    gateway.create_generic_item.return_value = "NEWNOTE"
    return gateway, _restore_service(gateway)


def _trashed_note(parent, text):
    from zotero_cli.core.zotero_item import ZoteroItem

    return ZoteroItem.from_raw_zotero_item(
        {
            "key": "OLDTRASH",
            "data": {"itemType": "note", "parentItem": parent, "note": text, "deleted": 1},
        }
    )


def test_a_trashed_note_already_in_the_trash_is_not_created_again():
    """The Web API hides a trashed child from its parent's listing, so the trash is asked."""
    gateway, service = _service_with(None, [_trashed_note("EXISTING1", "<p>gone</p>")])
    service._build_existing_item_indexes()
    report = RestoreReport()

    service._restore_note({"note": "<p>gone</p>", "deleted": 1}, "EXISTING1", report)

    gateway.create_generic_item.assert_not_called()
    assert report.items_trashed == 0


def test_a_trashed_note_that_is_not_in_the_trash_yet_is_created_there():
    gateway, service = _service_with(None, [_trashed_note("EXISTING1", "<p>other</p>")])
    service._build_existing_item_indexes()
    report = RestoreReport()

    service._restore_note({"note": "<p>gone</p>", "deleted": 1}, "EXISTING1", report)

    assert gateway.create_generic_item.call_args.args[0]["deleted"] == 1
    assert report.items_trashed == 1


def test_a_live_note_is_not_mistaken_for_a_trashed_one():
    """A live note with the same text does not stop the trashed one, nor the other way round."""
    live = {"key": "L1", "data": {"itemType": "note", "note": "<p>same</p>"}}
    gateway, service = _service_with(None, [], children=[live])
    service._build_existing_item_indexes()

    service._restore_note({"note": "<p>same</p>", "deleted": 1}, "EXISTING1", RestoreReport())
    service._restore_note({"note": "<p>same</p>"}, "EXISTING1", RestoreReport())

    assert gateway.create_generic_item.call_count == 1  # the live one exists; the trashed does not


def test_an_archived_trashed_article_matches_one_that_is_already_in_the_trash():
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway
    from zotero_cli.core.zotero_item import ZoteroItem

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_items.return_value = iter([])
    gateway.get_trash_items.return_value = iter(
        [
            ZoteroItem.from_raw_zotero_item(
                {
                    "key": "TRASHED1",
                    "data": {"itemType": "book", "title": "Gone book", "deleted": 1},
                }
            )
        ]
    )
    service = _restore_service(gateway)
    doi_index, title_index = service._build_existing_item_indexes()
    report = RestoreReport()

    service._restore_single_item(
        {"key": "OLD", "data": {"itemType": "book", "title": "Gone book", "deleted": 1}},
        zipfile.ZipFile(io.BytesIO(_empty_zip())),
        {},
        report,
        doi_index,
        title_index,
    )

    assert service.item_map["OLD"] == "TRASHED1"
    assert report.items_skipped_existing == 1
    gateway.create_generic_item.assert_not_called()


def _empty_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w"):
        pass
    return buffer.getvalue()


def test_an_attachment_is_created_from_what_the_archive_holds_about_it():
    from zotero_cli.core.services.restore_service import _attachment_payload

    data = {
        "key": "OLDKEY",
        "version": 7,
        "itemType": "attachment",
        "parentItem": "OLDPARENT",
        "collections": ["OLDCOL"],
        "relations": {"dc:relation": ["x"]},
        "md5": "abc",
        "mtime": 1,
        "dateAdded": "2026-01-01T00:00:00Z",
        "dateModified": "2026-01-02T00:00:00Z",
        "title": "Full Text PDF",
        "filename": "paper.pdf",
        "linkMode": "imported_url",
        "contentType": "application/pdf",
        "url": "https://example.org/x",
        "accessDate": "2026-08-23T18:51:17Z",
        "tags": [{"tag": "t", "type": 1}],
    }

    payload = _attachment_payload(data)

    assert payload == {
        "itemType": "attachment",
        "dateAdded": "2026-01-01T00:00:00Z",
        "dateModified": "2026-01-02T00:00:00Z",
        "title": "Full Text PDF",
        "filename": "paper.pdf",
        "linkMode": "imported_url",
        "contentType": "application/pdf",
        "url": "https://example.org/x",
        "accessDate": "2026-08-23T18:51:17Z",
        "tags": [{"tag": "t", "type": 1}],
    }


def test_an_attachment_without_a_title_is_created_with_an_empty_one_and_the_flags():
    from zotero_cli.core.services.restore_service import _attachment_payload

    payload = _attachment_payload({"itemType": "attachment", "deleted": 1}, ["NEWCOL"])

    assert payload["title"] == ""
    assert payload["deleted"] == 1
    assert payload["collections"] == ["NEWCOL"]


def _link_raw(link_mode="linked_url", **fields):
    return {
        "key": "LNK1",
        "data": {"itemType": "attachment", "linkMode": link_mode, "title": "Publisher", **fields},
    }


def test_a_web_link_is_recreated_under_its_parent_from_its_record(tmp_path):
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.create_generic_item.return_value = "NEWLINK"
    service = _restore_service(gateway)
    service._created.add("NEWPARENT")  # a parent this run made: nothing to match
    report = RestoreReport()

    service._restore_attachment(
        _link_raw(url="https://example.org/p"),
        _zaf_with_attachment(tmp_path, b"x"),
        {},
        "NEWPARENT",
        report,
    )

    payload = gateway.create_generic_item.call_args.args[0]
    assert payload["parentItem"] == "NEWPARENT"
    assert payload["url"] == "https://example.org/p"
    assert payload["linkMode"] == "linked_url"
    assert report.items_created == 1


def test_a_linked_file_keeps_its_path_and_a_link_that_exists_is_not_created_again(tmp_path):
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_item_children.return_value = [
        {
            "data": {
                "itemType": "attachment",
                "linkMode": "linked_url",
                "url": "https://example.org/p",
            }
        }
    ]
    gateway.create_generic_item.return_value = "NEWLINK"
    service = _restore_service(gateway)
    report = RestoreReport()
    zf = _zaf_with_attachment(tmp_path, b"x")

    service._restore_attachment(_link_raw(url="https://example.org/p"), zf, {}, "EXISTING1", report)
    service._restore_attachment(
        _link_raw("linked_file", path="/home/me/paper.pdf"), zf, {}, "EXISTING1", report
    )

    assert report.attachments_skipped_existing == 1
    assert gateway.create_generic_item.call_count == 1
    assert gateway.create_generic_item.call_args.args[0]["path"] == "/home/me/paper.pdf"


def test_a_dry_run_counts_a_link_and_writes_nothing(tmp_path):
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    service = _restore_service(gateway)
    service._created.add("NEWPARENT")
    report = RestoreReport(is_dry_run=True)

    service._restore_attachment(
        _link_raw(url="https://example.org/p"),
        _zaf_with_attachment(tmp_path, b"x"),
        {},
        "NEWPARENT",
        report,
    )

    assert report.items_created == 1
    gateway.create_generic_item.assert_not_called()


def test_a_stored_attachment_whose_file_is_not_in_the_archive_is_a_warning(tmp_path):
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    service = _restore_service(gateway)
    report = RestoreReport()
    raw = {
        "key": "ATT9",
        "data": {"itemType": "attachment", "linkMode": "imported_file", "title": "Lost"},
    }

    service._restore_attachment(
        raw, _zaf_with_attachment(tmp_path, b"x"), {"file_map": {}}, "P1", report
    )

    assert any("its file is not in the archive" in w for w in report.warnings)
    gateway.upload_attachment_item.assert_not_called()


ANNOTATION: Dict[str, Any] = {
    "key": "OLDANN",
    "data": {
        "key": "OLDANN",
        "version": 4,
        "itemType": "annotation",
        "parentItem": "OLDPDF",
        "annotationType": "highlight",
        "annotationText": "the text",
        "annotationComment": "",
        "annotationColor": "#ffd400",
        "annotationPageLabel": "1",
        "annotationSortIndex": "00000|002176|00328",
        "annotationPosition": '{"pageIndex":0,"rects":[[1,2,3,4]]}',
        "tags": [{"tag": "t"}],
        "relations": {},
        "dateAdded": "2026-08-31T01:38:56Z",
        "dateModified": "2026-08-31T01:38:56Z",
    },
}


def _annotation_service():
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.create_generic_item.return_value = "NEWANN"
    return gateway, _restore_service(gateway)


def test_an_annotation_is_created_under_the_restored_pdf_with_all_its_fields():
    """Issue #685: the real API accepts all five kinds as they were archived."""
    from zotero_cli.core.services.restore_service import _annotation_payload

    payload = _annotation_payload(ANNOTATION["data"], "NEWPDF")

    assert payload == {
        "itemType": "annotation",
        "dateAdded": "2026-08-31T01:38:56Z",
        "dateModified": "2026-08-31T01:38:56Z",
        "parentItem": "NEWPDF",
        "annotationType": "highlight",
        "annotationText": "the text",
        "annotationComment": "",
        "annotationColor": "#ffd400",
        "annotationPageLabel": "1",
        "annotationSortIndex": "00000|002176|00328",
        "annotationPosition": '{"pageIndex":0,"rects":[[1,2,3,4]]}',
        "tags": [{"tag": "t"}],
    }


def test_an_annotation_goes_under_the_new_key_of_its_attachment():
    gateway, service = _annotation_service()
    service.item_map["OLDPDF"] = "NEWPDF"
    service._created.add("NEWPDF")
    report = RestoreReport()

    service._restore_annotation(ANNOTATION, report)

    assert gateway.create_generic_item.call_args.args[0]["parentItem"] == "NEWPDF"
    assert report.items_created == 1
    gateway.get_item_children.assert_not_called()  # a PDF this run made has nothing to match


def test_an_annotation_whose_pdf_was_not_restored_is_a_warning_not_a_409():
    gateway, service = _annotation_service()
    report = RestoreReport()

    service._restore_annotation(ANNOTATION, report)

    assert any("its PDF was not restored" in w for w in report.warnings)
    gateway.create_generic_item.assert_not_called()
    assert report.errors == []


def test_an_annotation_the_pdf_already_has_is_not_created_again():
    gateway, service = _annotation_service()
    service.item_map["OLDPDF"] = "EXISTINGPDF"
    gateway.get_item_children.return_value = [
        {"key": "HAVE", "data": {k: v for k, v in ANNOTATION["data"].items() if k != "key"}}
    ]
    report = RestoreReport()

    service._restore_annotation(ANNOTATION, report)

    gateway.create_generic_item.assert_not_called()
    assert report.items_skipped_existing == 1


def test_a_different_annotation_on_an_existing_pdf_is_created():
    gateway, service = _annotation_service()
    service.item_map["OLDPDF"] = "EXISTINGPDF"
    other = {
        **ANNOTATION["data"],
        "annotationPosition": '{"pageIndex":3}',
        "itemType": "annotation",
    }
    gateway.get_item_children.return_value = [{"key": "OTHER", "data": other}]

    service._restore_annotation(ANNOTATION, RestoreReport())

    gateway.create_generic_item.assert_called_once()


def test_a_dry_run_counts_an_annotation_and_writes_nothing():
    gateway, service = _annotation_service()
    service.item_map["OLDPDF"] = "DRY_RUN_OLDPDF"
    service._created.add("DRY_RUN_OLDPDF")
    report = RestoreReport(is_dry_run=True)

    service._restore_annotation(ANNOTATION, report)

    assert report.items_created == 1
    gateway.create_generic_item.assert_not_called()


def test_annotations_are_restored_after_their_attachments():
    _, service = _annotation_service()
    items = [
        {"key": "A", "data": {"itemType": "annotation"}},
        {"key": "N", "data": {"itemType": "note"}},
        {"key": "P", "data": {"itemType": "journalArticle"}},
        {"key": "F", "data": {"itemType": "attachment"}},
    ]

    ordered = [i["key"] for i in service._sort_items_by_hierarchy(items)]

    assert ordered == ["P", "N", "F", "A"]


def test_a_restored_attachment_remembers_its_new_key(tmp_path):
    gateway, service = _annotation_service()
    gateway.upload_attachment_item.return_value = "NEWPDF"
    zf = _zaf_with_attachment(tmp_path, b"%PDF-1.7 x")
    manifest = {"file_map": {"OLDPDF": {"path": "files/ATT1/paper.pdf"}}}

    service._restore_attachment(
        {"key": "OLDPDF", "data": {"linkMode": "imported_file"}},
        zf,
        manifest,
        "NEWPARENT",
        RestoreReport(),
    )

    assert service.item_map["OLDPDF"] == "NEWPDF"
    assert "NEWPDF" in service._created


def test_an_attachment_that_already_exists_is_mapped_to_the_existing_key(tmp_path):
    import hashlib

    payload = b"%PDF-1.7 same"
    gateway, service = _annotation_service()
    gateway.get_item_children.return_value = [
        {
            "key": "EXISTINGPDF",
            "data": {
                "itemType": "attachment",
                "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
            },
        }
    ]
    zf = _zaf_with_attachment(tmp_path, payload)
    manifest = {"file_map": {"OLDPDF": {"path": "files/ATT1/paper.pdf"}}}

    service._restore_attachment(
        {"key": "OLDPDF", "data": {"linkMode": "imported_file"}},
        zf,
        manifest,
        "EXISTING1",
        RestoreReport(),
    )

    assert service.item_map["OLDPDF"] == "EXISTINGPDF"
    gateway.upload_attachment_item.assert_not_called()


def _relations_service(library=None, source=None):
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway
    from zotero_cli.core.models import LibraryRef

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.update_item.return_value = True
    service = _restore_service(gateway)
    service.library = LibraryRef(*library) if library else None
    service._source = LibraryRef(*source) if source else None
    service.item_map.update({"OLDAAAAA": "NEWAAAAA", "OLDBBBBB": "NEWBBBBB"})
    return gateway, service


def _uri(scope, library_id, key):
    return f"http://zotero.org/{scope}/{library_id}/items/{key}"


def test_a_related_item_link_names_the_target_library_and_the_new_key():
    """Issue #686: it named the old library and the old key."""
    _, service = _relations_service(library=("user", "42"), source=("group", "777"))

    new = service._new_uri(_uri("groups", "777", "OLDBBBBB"), {"key": "OLDAAAAA"}, RestoreReport())

    assert new == _uri("users", "42", "NEWBBBBB")


def test_a_single_link_stored_as_a_string_is_mapped_to_a_list():
    """The Web API returns one link as a plain string, several as a list."""
    _, service = _relations_service(library=("group", "888"), source=("group", "777"))
    raw = {"key": "OLDAAAAA", "data": {"relations": {}}}

    mapped = service._map_relations(
        {"dc:relation": _uri("groups", "777", "OLDBBBBB")}, raw, RestoreReport()
    )

    assert mapped == {"dc:relation": [_uri("groups", "888", "NEWBBBBB")]}


def test_a_link_that_is_not_an_item_of_the_archive_s_library_is_kept():
    _, service = _relations_service(library=("user", "42"), source=("group", "777"))
    other_library = _uri("groups", "9999", "OLDBBBBB")  # the same key, another library

    kept = service._new_uri(other_library, {"key": "X"}, RestoreReport())
    not_an_item = service._new_uri("http://example.org/something", {"key": "X"}, RestoreReport())

    assert kept == other_library
    assert not_an_item == "http://example.org/something"


def test_a_link_to_a_missing_item_of_the_library_is_dropped_with_a_warning():
    _, service = _relations_service(library=("user", "42"), source=("group", "777"))
    report = RestoreReport()
    raw = {"key": "OLDAAAAA", "data": {"itemType": "book", "title": "A"}}

    dropped = service._new_uri(_uri("groups", "777", "GHOSTKEY"), raw, report)

    assert dropped is None
    assert any("GHOSTKEY" in w and "link dropped" in w for w in report.warnings)


def test_an_archive_that_does_not_say_where_it_is_from_keeps_what_it_cannot_map():
    """Before format 1.2 there is no library to compare: only keys the archive holds change."""
    _, service = _relations_service(library=("user", "42"), source=None)
    report = RestoreReport()

    unknown = service._new_uri(_uri("groups", "777", "GHOSTKEY"), {"key": "X"}, report)
    known = service._new_uri(_uri("groups", "777", "OLDBBBBB"), {"key": "X"}, report)

    assert unknown == _uri("groups", "777", "GHOSTKEY")
    assert known == _uri("users", "42", "NEWBBBBB")
    assert report.warnings == []


def test_without_a_target_library_only_the_key_changes():
    _, service = _relations_service(library=None, source=("group", "777"))

    new = service._new_uri(_uri("groups", "777", "OLDBBBBB"), {"key": "X"}, RestoreReport())

    assert new == _uri("groups", "777", "NEWBBBBB")


def test_only_items_this_run_created_get_their_links_set():
    gateway, service = _relations_service(library=("user", "42"), source=("group", "777"))
    service._created.add("NEWAAAAA")  # created now; NEWBBBBB already existed
    items = [
        {
            "key": "OLDAAAAA",
            "data": {"relations": {"dc:relation": [_uri("groups", "777", "OLDBBBBB")]}},
        },
        {
            "key": "OLDBBBBB",
            "data": {"relations": {"dc:relation": [_uri("groups", "777", "OLDAAAAA")]}},
        },
    ]
    report = RestoreReport()

    service._restore_relations(items, report)

    gateway.update_item.assert_called_once_with(
        "NEWAAAAA", 0, {"relations": {"dc:relation": [_uri("users", "42", "NEWBBBBB")]}}
    )
    assert report.relations_restored == 1


def test_a_failed_update_of_the_links_is_an_error():
    gateway, service = _relations_service(library=("user", "42"), source=("group", "777"))
    gateway.update_item.return_value = False
    service._created.add("NEWAAAAA")
    report = RestoreReport()

    service._restore_relations(
        [
            {
                "key": "OLDAAAAA",
                "data": {
                    "itemType": "book",
                    "relations": {"dc:relation": [_uri("groups", "777", "OLDBBBBB")]},
                },
            }
        ],
        report,
    )

    assert report.relations_restored == 0
    assert any("related items" in e for e in report.errors)


def test_a_note_keeps_its_dates_when_it_has_them_and_invents_none():
    """Issue #687: the Web API keeps dateAdded and dateModified given on create."""
    from zotero_cli.core.services.restore_service import _note_payload

    dated = _note_payload(
        {
            "note": "<p>x</p>",
            "dateAdded": "2019-05-06T07:08:09Z",
            "dateModified": "2020-01-01T00:00:00Z",
        }
    )
    undated = _note_payload({"note": "<p>x</p>"})

    assert dated["dateAdded"] == "2019-05-06T07:08:09Z"
    assert dated["dateModified"] == "2020-01-01T00:00:00Z"
    assert "dateAdded" not in undated
    assert "dateModified" not in undated


def test_an_article_is_created_with_its_original_dates():
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_items.return_value = iter([])
    gateway.create_generic_item.return_value = "NEWKEY"
    service = _restore_service(gateway)
    doi_index, title_index = service._build_existing_item_indexes()
    raw = {
        "key": "OLD",
        "version": 9,
        "data": {
            "itemType": "journalArticle",
            "title": "Paper",
            "dateAdded": "2026-08-23T18:24:43Z",
            "dateModified": "2026-09-01T10:00:00Z",
        },
    }

    service._restore_single_item(
        raw, zipfile.ZipFile(io.BytesIO(_empty_zip())), {}, RestoreReport(), doi_index, title_index
    )

    sent = gateway.create_generic_item.call_args.args[0]
    assert sent["dateAdded"] == "2026-08-23T18:24:43Z"
    assert sent["dateModified"] == "2026-09-01T10:00:00Z"
    assert "version" not in sent
    assert "key" not in sent


def _existing(key, title, doi, collections, url=""):
    from zotero_cli.core.zotero_item import ZoteroItem

    return ZoteroItem.from_raw_zotero_item(
        {
            "key": key,
            "data": {
                "itemType": "journalArticle",
                "title": title,
                "DOI": doi,
                "collections": collections,
                "url": url,
            },
        }
    )


def _two_copies():
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    first = _existing("FIRST001", "Same paper", "10.1/x", ["COL1"])
    second = _existing("SECOND01", "Same paper", "10.1/x", ["COL2"])
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_items.return_value = iter([first, second])
    gateway.get_trash_items.return_value = iter([])
    service = _restore_service(gateway)
    doi_index, title_index = service._build_existing_item_indexes()
    return service, doi_index, title_index


def test_two_archived_copies_match_two_existing_copies_not_one():
    """Issue #699."""
    service, doi_index, title_index = _two_copies()
    data = {"DOI": "10.1/x", "title": "Same paper"}

    a = service._find_existing_item(data, doi_index, title_index, ["COL1"])
    b = service._find_existing_item(data, doi_index, title_index, ["COL2"])

    assert (a.key, b.key) == ("FIRST001", "SECOND01")


def test_the_copy_filed_in_the_same_collections_wins_whatever_the_order():
    service, doi_index, title_index = _two_copies()
    data = {"DOI": "10.1/x", "title": "Same paper"}

    match = service._find_existing_item(data, doi_index, title_index, ["COL2"])

    assert match.key == "SECOND01"


def test_a_match_is_used_once_and_the_next_archived_copy_gets_none():
    service, doi_index, title_index = _two_copies()
    data = {"DOI": "10.1/x", "title": "Same paper"}

    for _ in range(2):
        assert service._find_existing_item(data, doi_index, title_index, []) is not None
    third = service._find_existing_item(data, doi_index, title_index, [])

    assert third is None  # a third copy is created, not folded into the other two


def test_the_url_breaks_a_tie_between_copies_in_the_same_collections():
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    one = _existing("ONE00001", "Same paper", "10.1/x", ["COL1"], "https://a.example/1")
    two = _existing("TWO00001", "Same paper", "10.1/x", ["COL1"], "https://b.example/2")
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_items.return_value = iter([one, two])
    gateway.get_trash_items.return_value = iter([])
    service = _restore_service(gateway)
    doi_index, title_index = service._build_existing_item_indexes()

    match = service._find_existing_item(
        {"DOI": "10.1/x", "title": "Same paper", "url": "https://b.example/2"},
        doi_index,
        title_index,
        ["COL1"],
    )

    assert match.key == "TWO00001"


def test_an_archived_doi_that_matches_only_claimed_items_does_not_fall_back_to_the_title():
    """A different paper with the same title must not be taken for the copy that is missing."""
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway

    only = _existing("ONLY0001", "Same title", "10.1/x", [])
    other = _existing("OTHER001", "Same title", "10.9/other", [])
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_items.return_value = iter([only, other])
    gateway.get_trash_items.return_value = iter([])
    service = _restore_service(gateway)
    doi_index, title_index = service._build_existing_item_indexes()
    data = {"DOI": "10.1/x", "title": "Same title"}

    first = service._find_existing_item(data, doi_index, title_index, [])
    second = service._find_existing_item(data, doi_index, title_index, [])

    assert first.key == "ONLY0001"
    assert second is None
