"""`system restore --key-map` (Issue #721): every item, collection and saved search of an
archive is accounted for, and each key it names is the right item in the restored library.

Built on the round trip of `test_restore_roundtrip.py`: the sample library (nested
collections, two copies of one paper, child and stand-alone notes, files, annotations, saved
searches, a trash) backed up through the real client and restored into the fake Web API."""

import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from tests.unit.core.test_restore_roundtrip import (  # noqa: F401  (trip is a fixture)
    Trip,
    col_path,
    ident,
    trip,
)
from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.services.restore_report import (
    RestoreReport,
    check_key_map_path,
    key_map_document,
    write_key_map,
)


def _archived(archive: Path, member: str) -> List[Dict[str, Any]]:
    with zipfile.ZipFile(archive) as zf:
        return json.loads(zf.read(member)) if member in zf.namelist() else []


def _children_signature(data: Dict[str, Any]) -> str:
    """What identifies a note or an annotation whatever its keys are."""
    text = data.get("note") or data.get("annotationText") or data.get("annotationPosition") or ""
    return f"{data.get('itemType')}|{data.get('filename', '')}|{str(text).split('data-attachment-key')[0]}"


def test_everything_in_the_archive_is_in_the_map_exactly_once(trip: Trip) -> None:  # noqa: F811
    report = trip.report

    assert set(report.item_keys) == {r["key"] for r in _archived(trip.archive, "data.json")}
    assert set(report.collection_keys) == {
        r["key"] for r in _archived(trip.archive, "collections.json")
    }
    assert set(report.search_keys) == {r["key"] for r in _archived(trip.archive, "searches.json")}
    for outcome in [
        *report.item_keys.values(),
        *report.collection_keys.values(),
        *report.search_keys.values(),
    ]:
        assert outcome["status"] in ("created", "existing", "not_restored")
        assert (outcome["key"] is None) == (outcome["status"] == "not_restored")


def test_into_an_empty_library_what_the_archive_holds_is_created_under_new_keys(
    trip: Trip,  # noqa: F811
) -> None:
    created = {k: v for k, v in trip.report.item_keys.items() if v["status"] == "created"}

    # every item that came back is in the map under the key it has in the target now
    assert {v["key"] for v in created.values()} >= set(trip.target.lib.items)
    assert len({v["key"] for v in created.values()}) == len(created)  # one new item each
    assert not any(str(v["key"]).startswith("DRY_RUN") for v in created.values())


def test_every_new_key_names_the_same_thing_as_the_old_one(trip: Trip) -> None:  # noqa: F811
    archived = {r["key"]: r for r in _archived(trip.archive, "data.json")}
    wrong = []
    for old, outcome in trip.report.item_keys.items():
        if outcome["key"] is None:
            continue
        new_key = str(outcome["key"])
        before, after = archived[old]["data"], trip.target.lib.items[new_key]["data"]
        if before["itemType"] in ("note", "annotation", "attachment"):
            # an attachment archived without a file name (an image in a note) is given one
            compared = {
                **after,
                "filename": after.get("filename") if before.get("filename") else "",
            }
            same = _children_signature(before) == _children_signature(compared)
            if before.get("parentItem"):
                parent = trip.report.item_keys[before["parentItem"]]["key"]
                same = same and after.get("parentItem") == parent
        else:
            same = ident(trip.source, old) == ident(trip.target.lib, new_key)
        if not same or outcome["item_type"] != before["itemType"]:
            wrong.append((old, outcome["key"], before["itemType"]))

    assert wrong == []


def test_notes_and_annotations_are_mapped_too(trip: Trip) -> None:  # noqa: F811
    """They were not part of the restore's own parent lookup."""
    by_type: Dict[str, List[str]] = {}
    for outcome in trip.report.item_keys.values():
        by_type.setdefault(outcome["item_type"], []).append(outcome["status"])

    assert "created" in by_type["note"]
    assert "created" in by_type["annotation"]
    # a child note, two copies' notes and their annotations
    for key in ("TAGNOTE1", "DUPANTE1", "DUPBNTE1", "DUPAANN1", "DUPBANN1"):
        assert trip.report.item_keys[key]["status"] == "created", key


def test_two_copies_of_one_paper_keep_their_own_keys(trip: Trip) -> None:  # noqa: F811
    keys = trip.report.item_keys
    for old in ("DUPA0001", "DUPAPDF1", "DUPANTE1", "DUPAANN1"):
        assert keys[old]["key"] != keys[old.replace("DUPA", "DUPB")]["key"]
    note_a = trip.target.lib.items[str(keys["DUPANTE1"]["key"])]["data"]
    assert note_a["parentItem"] == keys["DUPA0001"]["key"]


def test_collections_and_searches_name_the_right_ones(trip: Trip) -> None:  # noqa: F811
    for old, outcome in trip.report.collection_keys.items():
        assert col_path(trip.source, old) == col_path(trip.target.lib, str(outcome["key"]))
    for old, outcome in trip.report.search_keys.items():
        if outcome["key"]:
            assert (
                trip.target.lib.searches[outcome["key"]]["data"]["name"]
                == trip.source.searches[old]["data"]["name"]
            )
    # the search that names a collection which is gone is said to be missing, not dropped
    assert trip.report.search_keys["SRCH0012"] == {"key": None, "status": "not_restored"}


def test_restoring_again_finds_the_same_keys_as_existing(trip: Trip) -> None:  # noqa: F811
    first = trip.report

    again = trip.restore_again()

    for table in ("item_keys", "collection_keys", "search_keys"):
        before, after = getattr(first, table), getattr(again, table)
        assert set(after) == set(before)
        changed = {k: (before[k], after[k]) for k in before if before[k]["key"] != after[k]["key"]}
        assert changed == {}, table
        assert {v["status"] for v in after.values()} <= {"existing", "not_restored"}, table


def test_what_has_to_be_created_again_gets_the_new_key_and_the_rest_keeps_its_own(
    trip: Trip,  # noqa: F811
) -> None:
    first = trip.report.item_keys
    gone = first["DUPAANN1"]["key"], first["TAGNOTE1"]["key"]
    for key in gone:
        del trip.target.lib.items[str(key)]

    again = trip.restore_again().item_keys

    for old, was in zip(("DUPAANN1", "TAGNOTE1"), gone):
        assert again[old]["status"] == "created"
        assert again[old]["key"] != was
        assert str(again[old]["key"]) in trip.target.lib.items
    assert again["DUPBANN1"] == {**first["DUPBANN1"], "status": "existing"}
    assert again["DUPA0001"]["key"] == first["DUPA0001"]["key"]


def test_an_item_that_fails_is_not_restored_and_the_map_says_it_is_incomplete(
    trip: Trip,  # noqa: F811
) -> None:
    # both copies of the paper and what hangs on them are gone, and creating them fails (with
    # one copy left, the restore would rightly match the other to it, one to one)
    lost = [f"DUP{x}{kind}" for x in "AB" for kind in ("0001", "PDF1", "NTE1", "ANN1")]
    for old in lost:
        del trip.target.lib.items[str(trip.report.item_keys[old]["key"])]
    original = trip.target.create_generic_item
    trip.target.create_generic_item = lambda data: (  # type: ignore[method-assign]
        None if data.get("title") == "The same paper twice" else original(data)
    )

    report = trip.restore_again()
    document = key_map_document(report, "zotero-cli test")

    assert report.errors
    assert document["complete"] is False
    for old in lost:
        assert report.item_keys[old]["key"] is None, old
        assert report.item_keys[old]["status"] == "not_restored", old
    # everything else is still there and still mapped
    assert report.item_keys["TAGNOTE1"]["status"] == "existing"


def test_with_one_copy_of_a_paper_left_the_map_says_which_item_the_restore_took_it_for(
    trip: Trip,  # noqa: F811
) -> None:
    first = trip.report.item_keys
    survivor = first["DUPB0001"]["key"]
    del trip.target.lib.items[str(first["DUPA0001"]["key"])]

    keys = trip.restore_again().item_keys

    # one existing item stands for one archived copy; the other copy is created
    assert sorted(str(keys[k]["status"]) for k in ("DUPA0001", "DUPB0001")) == [
        "created",
        "existing",
    ]
    assert survivor in (keys["DUPA0001"]["key"], keys["DUPB0001"]["key"])
    assert keys["DUPA0001"]["key"] != keys["DUPB0001"]["key"]


def test_a_preview_has_no_keys(trip: Trip) -> None:  # noqa: F811
    from typing import cast

    from zotero_cli.core.services.restore_service import RestoreService

    repository: Any = cast(Any, trip.target)

    report = RestoreService(repository, repository, repository, repository).restore_archive(
        str(trip.archive), dry_run=True
    )

    assert (report.item_keys, report.collection_keys, report.search_keys) == ({}, {}, {})


def test_the_document_names_both_libraries(trip: Trip) -> None:  # noqa: F811
    document = key_map_document(trip.report, "zotero-cli 9.9.9")

    assert (document["format"], document["version"]) == ("zotero-cli-key-map", 1)
    assert document["generator"] == "zotero-cli 9.9.9"
    assert document["complete"] is True
    assert document["source_library"]["type"] == "group"
    assert document["target_library"] == {"type": "user", "id": "8888"}
    assert document["items"] == trip.report.item_keys
    json.dumps(document)


def test_an_archive_that_cannot_be_read_gives_an_empty_incomplete_map(tmp_path: Path) -> None:
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import (
        AttachmentRepository,
        CollectionRepository,
        ItemRepository,
        NoteRepository,
    )
    from zotero_cli.core.services.restore_service import RestoreService

    broken = tmp_path / "broken.zaf"
    broken.write_bytes(b"not a zip")
    service = RestoreService(
        create_autospec(ItemRepository, instance=True),
        create_autospec(CollectionRepository, instance=True),
        create_autospec(NoteRepository, instance=True),
        create_autospec(AttachmentRepository, instance=True),
    )

    report = service.restore_archive(str(broken))

    document = key_map_document(report, "x")
    assert (document["complete"], document["items"]) == (False, {})


# --- the file ---------------------------------------------------------------------------


def test_the_map_is_written_whole_and_replaces_an_older_one(tmp_path: Path) -> None:
    target = tmp_path / "keys.json"
    target.write_text("old")
    target.chmod(0o640)

    write_key_map(str(target), {"title": "ação"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"title": "ação"}
    assert target.stat().st_mode & 0o777 == 0o640
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keys.json"]


def test_a_failed_write_leaves_the_older_map_and_no_stray_file(tmp_path: Path) -> None:
    target = tmp_path / "keys.json"
    target.write_text("old")

    with pytest.raises(TypeError):
        write_key_map(str(target), {"not json": object()})

    assert target.read_text() == "old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keys.json"]


@pytest.mark.parametrize("name", ["", "missing/keys.json"])
def test_a_path_that_cannot_be_written_is_refused(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "a.zaf"
    archive.write_bytes(b"PK")

    with pytest.raises(UsageError):
        check_key_map_path(str(tmp_path / name), str(archive))


def test_the_archive_itself_is_never_overwritten(tmp_path: Path) -> None:
    archive = tmp_path / "a.zaf"
    archive.write_bytes(b"PK")
    link = tmp_path / "keys.json"
    link.symlink_to(archive)

    for path in (archive, link):
        with pytest.raises(UsageError, match="must not be the archive"):
            check_key_map_path(str(path), str(archive))


def test_an_unwritable_directory_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("os.access", lambda *_: False)

    with pytest.raises(UsageError, match="not writable"):
        check_key_map_path(str(tmp_path / "keys.json"), str(tmp_path / "a.zaf"))


def test_an_empty_report_is_a_complete_map_of_nothing() -> None:
    document = key_map_document(RestoreReport(), "x")

    assert document["complete"] is True
    assert document["source_library"] is None
