import io
import json
import zipfile
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.restore_service import RestoreService
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


@pytest.fixture
def mock_orchestrator():
    return MagicMock()


def test_restore_service_dry_run(dummy_zaf, tmp_path, mock_orchestrator):
    zaf_path = tmp_path / "restore.zaf"
    zaf_path.write_bytes(dummy_zaf.getvalue())

    mock_gw = MagicMock()
    mock_gw.get_all_collections.return_value = []
    mock_gw.get_all_items.return_value = []

    service = RestoreService(mock_gw, mock_orchestrator)
    report = service.restore_archive(str(zaf_path), dry_run=True)

    assert report.is_dry_run is True
    assert report.items_created == 1
    assert report.attachments_uploaded == 1


def test_restore_collections_hierarchy(mock_gateway, mock_orchestrator):
    service = RestoreService(mock_gateway, mock_orchestrator)

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


def test_restore_child_parent_not_found(mock_gateway, mock_orchestrator):
    service = RestoreService(mock_gateway, mock_orchestrator)
    # Child with parent that is not in map
    child_raw = {"key": "ATT1", "data": {"itemType": "attachment", "parentItem": "MISSING"}}

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport()
    # Should return early and not crash
    service._restore_child_item(child_raw, MagicMock(), {}, report)
    assert not mock_gateway.upload_attachment.called


def test_restore_service_idempotency_none(mock_gateway, mock_orchestrator):
    service = RestoreService(mock_gateway, mock_orchestrator)
    # Data with no DOI or Title
    data = {"itemType": "journalArticle"}
    result = service._find_existing_item(data, {}, {})
    assert result is None


def test_restore_attachment_mode_mismatch(dummy_zaf, tmp_path, mock_gateway, mock_orchestrator):
    zaf_path = tmp_path / "mode.zaf"
    zaf_path.write_bytes(dummy_zaf.getvalue())
    service = RestoreService(mock_gateway, mock_orchestrator)
    # web_page or similar mode that we don't upload
    child_raw = {"key": "ATT1", "data": {"itemType": "attachment", "linkMode": "linked_url"}}

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport()
    with zipfile.ZipFile(zaf_path, "r") as zf:
        service._restore_attachment(child_raw, zf, {}, "PARENT", report)
    assert not mock_gateway.upload_attachment.called


def test_restore_item_creation_failure(mock_gateway, mock_orchestrator):
    from zotero_cli.core.services.restore_service import RestoreReport

    service = RestoreService(mock_gateway, mock_orchestrator)
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


def test_restore_collections_match_existing(mock_gateway, mock_orchestrator):
    service = RestoreService(mock_gateway, mock_orchestrator)
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


def test_restore_note_creation(mock_gateway, mock_orchestrator):
    service = RestoreService(mock_gateway, mock_orchestrator)
    item_key = "K1"
    note_data = {"note": "New note"}
    # Mock no existing notes
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport(is_dry_run=False)
    service._restore_note(note_data, item_key, report)

    mock_gateway.create_note.assert_called_once_with(item_key, "New note")


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


def test_restore_service_idempotency_doi_none(mock_gateway, mock_orchestrator):
    service = RestoreService(mock_gateway, mock_orchestrator)

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


def test_restore_collections_failure(mock_gateway, mock_orchestrator):
    service = RestoreService(mock_gateway, mock_orchestrator)
    colls = [{"key": "C1", "data": {"name": "Fail", "parentCollection": None}}]
    mock_gateway.get_all_collections.return_value = []
    # Mock creation failure
    mock_gateway.create_collection.return_value = None

    from zotero_cli.core.services.restore_service import RestoreReport

    report = RestoreReport(is_dry_run=False)
    service._restore_collections(colls, report)

    assert len(report.errors) == 1
    assert "Failed to create collection" in report.errors[0]


def test_restore_collections_fetches_existing_once_for_many_collections(
    mock_gateway, mock_orchestrator
):
    """Regression test for Issue #277: _restore_collections must call
    get_all_collections() once for the whole batch, not once per
    collection being restored."""
    service = RestoreService(mock_gateway, mock_orchestrator)
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


def test_build_existing_item_indexes_single_scan(mock_gateway, mock_orchestrator):
    """Regression test for Issue #277: the DOI/title indexes must come from
    one get_all_items() pass, and _find_existing_item must consult those
    indexes rather than re-scanning the library per item."""
    from zotero_cli.core.zotero_item import ZoteroItem

    item1 = ZoteroItem(
        key="P1", version=1, item_type="journalArticle", doi="10.1/ABC", title="Paper One"
    )
    item2 = ZoteroItem(key="P2", version=1, item_type="journalArticle", title="Paper Two")
    mock_gateway.get_all_items.return_value = [item1, item2]

    service = RestoreService(mock_gateway, mock_orchestrator)
    doi_index, title_index = service._build_existing_item_indexes()

    mock_gateway.get_all_items.assert_called_once()
    assert doi_index["10.1/abc"] is item1
    assert title_index["paper two"] is item2

    # DOI match (case/prefix-insensitive via normalize_doi)
    match = service._find_existing_item(
        {"DOI": "https://doi.org/10.1/ABC"}, doi_index, title_index
    )
    assert match is item1

    # Title fallback when DOI doesn't match anything indexed
    match = service._find_existing_item(
        {"DOI": "10.9/unrelated", "title": "Paper Two"}, doi_index, title_index
    )
    assert match is item2

    mock_gateway.get_all_items.assert_called_once()  # still only the one scan
    mock_gateway.get_items_by_doi.assert_not_called()


def test_restore_archive_builds_indexes_once_for_multiple_items(
    dummy_zaf, tmp_path, mock_orchestrator
):
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

    service = RestoreService(mock_gw, mock_orchestrator)
    report = service.restore_archive(str(zaf_path), dry_run=False)

    mock_gw.get_all_items.assert_called_once()
    mock_gw.get_items_by_doi.assert_not_called()
    assert report.items_created == 3
