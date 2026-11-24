"""A backup restored into an empty library must give back the library (tracking issue #679).

The sample library of `tests/zotero_fake.py` (nested collections, articles, notes with tags,
a standalone note and file, snapshots, annotated PDFs, related items, dates, a trash) is backed
up with `--trash` through the real client against the fake Web API, then restored through the
real `RestoreService` into a `FakeTarget`, which answers the repository calls the way the Web
API does. Keys change on a restore, so source and target are compared through views that do not
use them: collections by path, items by their own fields and their parent's title.

The tests that pass pin what already restores correctly. Each strict `xfail` is a finding of
the live round trip on the `teststr` group (2026-11-24), named after the issue that fixes it;
fixing it removes the marker, and a strict xfail that starts to pass fails until it is removed.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import pytest

from tests.zotero_fake import GROUP, FakeLibrary, FakeTarget, FakeZoteroServer, populate
from zotero_cli.core.services.restore_service import RestoreReport, RestoreService
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.infra.zotero_api import ZoteroAPIClient


def finding(issue: int, why: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"#{issue}: {why}")


# --- the round trip -----------------------------------------------------------------------


@dataclass
class Trip:
    source: FakeLibrary
    target: FakeTarget
    archive: Path
    report: RestoreReport
    restore_again: Callable[[], RestoreReport]


@pytest.fixture
def trip(tmp_path: Path) -> Trip:
    server = FakeZoteroServer()
    source = server.register(populate(FakeLibrary(*GROUP, name="Lab Group")))
    client = ZoteroAPIClient("key", source.library_id, source.library_type)
    client.http.session = server.session()  # type: ignore[assignment]
    # What the live round trip had: a note trashed on its own, under an article that is not
    source.add_item(
        "TRSHNTE1",
        "note",
        parent="JRN00001",
        note="<p>trashed on its own</p>",
        tags=[{"tag": "was-trashed"}],
        deleted=True,
    )
    archive = tmp_path / "library.zaf"
    GatewayFactory.get_backup_service(client).backup_system(str(archive), include_trash=True)
    target = FakeTarget()

    def restore() -> RestoreReport:
        repository: Any = cast(Any, target)
        service = RestoreService(repository, repository, repository, repository)
        return service.restore_archive(str(archive))

    return Trip(source, target, archive, restore(), restore)


# --- views that do not depend on keys -----------------------------------------------------

CHILD_TYPES = ("note", "attachment", "annotation")
VOLATILE = {
    "key",
    "version",
    "dateAdded",
    "dateModified",
    "parentItem",
    "collections",
    "relations",
    "md5",
    "mtime",
    "deleted",
    "parentCollection",
}


def col_path(lib: FakeLibrary, key: str) -> str:
    parts: List[str] = []
    current: Optional[str] = key
    while current and current in lib.collections:
        parts.append(lib.collections[current]["data"]["name"])
        current = lib.collections[current]["data"].get("parentCollection") or None
    return "/".join(reversed(parts))


def paths(lib: FakeLibrary, data: Dict[str, Any]) -> List[str]:
    return sorted(col_path(lib, k) for k in data.get("collections", []))


def ident(lib: FakeLibrary, key: Optional[str]) -> Optional[str]:
    if key is None or key not in lib.items:
        return None if key is None else f"UNRESOLVED:{key}"
    d = lib.items[key]["data"]
    text = d.get("title") or re.sub(r"<[^>]+>", " ", d.get("note", ""))[:60].strip()
    return f"{d['itemType']}|{text}|{d.get('DOI', '')}|{d.get('date', '')}"


def dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def collection_tree(lib: FakeLibrary) -> List[str]:
    return sorted(col_path(lib, k) for k in lib.collections)


def articles(lib: FakeLibrary) -> List[str]:
    found = []
    for key, raw in lib.items.items():
        d = raw["data"]
        if d["itemType"] in CHILD_TYPES:
            continue
        record = {k: v for k, v in d.items() if k not in VOLATILE}
        record["_collections"] = paths(lib, d)
        found.append(dump(record))
    return sorted(found)


def stored_files(lib: FakeLibrary) -> List[Tuple[Optional[str], str]]:
    """(parent, file hash) of every attachment whose file is stored in Zotero."""
    import hashlib

    return sorted(
        (ident(lib, r["data"].get("parentItem")) or "", hashlib.sha256(lib.files[k]).hexdigest())
        for k, r in lib.items.items()
        if r["data"]["itemType"] == "attachment"
        and "parentItem" in r["data"]
        and k in lib.files
        and r["data"].get("linkMode") != "embedded_image"
    )


def standalone_notes(lib: FakeLibrary) -> List[str]:
    return sorted(
        dump((r["data"]["note"], paths(lib, r["data"])))
        for r in lib.items.values()
        if r["data"]["itemType"] == "note" and "parentItem" not in r["data"]
    )


def standalone_files(lib: FakeLibrary) -> List[str]:
    import hashlib

    return sorted(
        dump((hashlib.sha256(lib.files[k]).hexdigest(), paths(lib, r["data"])))
        for k, r in lib.items.items()
        if r["data"]["itemType"] == "attachment"
        and "parentItem" not in r["data"]
        and k in lib.files
    )


def note_tags(lib: FakeLibrary) -> List[str]:
    return sorted(
        dump(
            (ident(lib, r["data"].get("parentItem")), r["data"]["note"], r["data"].get("tags", []))
        )
        for r in lib.items.values()
        if r["data"]["itemType"] == "note" and "parentItem" in r["data"]
    )


def trash_state(lib: FakeLibrary) -> List[str]:
    """Whether each article and each note that has a parent is in the trash."""
    found = []
    for key, raw in lib.items.items():
        d = raw["data"]
        if d["itemType"] in ("journalArticle", "book", "thesis") or (
            d["itemType"] == "note" and "parentItem" in d
        ):
            found.append(dump((ident(lib, key), lib.is_trashed(key))))
    return sorted(found)


def attachments(lib: FakeLibrary) -> List[str]:
    import hashlib

    fields = ("title", "filename", "linkMode", "url", "accessDate", "contentType", "tags")
    found = []
    for key, raw in lib.items.items():
        d = raw["data"]
        if d["itemType"] != "attachment" or d.get("linkMode") == "embedded_image":
            continue
        record: Dict[str, Any] = {f: d.get(f) for f in fields}
        record["_parent"] = ident(lib, d.get("parentItem"))
        record["_collections"] = paths(lib, d)
        record["_sha256"] = hashlib.sha256(lib.files[key]).hexdigest() if key in lib.files else None
        found.append(dump(record))
    return sorted(found)


def annotations(lib: FakeLibrary) -> List[str]:
    fields = ("annotationType", "annotationText", "annotationComment", "annotationColor")
    return sorted(
        dump(({f: r["data"].get(f) for f in fields}, ident(lib, r["data"]["parentItem"])))
        for r in lib.items.values()
        if r["data"]["itemType"] == "annotation"
    )


def relations(lib: FakeLibrary) -> List[str]:
    found = []
    for key, raw in lib.items.items():
        for predicate, targets in raw["data"].get("relations", {}).items():
            for uri in [targets] if isinstance(targets, str) else targets:
                found.append(dump((ident(lib, key), predicate, ident(lib, uri.rsplit("/", 1)[-1]))))
    return sorted(found)


def dates(lib: FakeLibrary) -> List[str]:
    return sorted(
        dump((ident(lib, k), r["data"].get("dateAdded"), r["data"].get("dateModified")))
        for k, r in lib.items.items()
        if r["data"]["itemType"] in ("journalArticle", "book", "thesis", "note")
    )


def assert_same(view: Callable[[FakeLibrary], Any], trip: Trip) -> None:
    """The restored library, seen through `view`, is the library that was backed up."""
    expected = view(trip.source)
    actual = view(trip.target.lib)
    assert actual == expected


# =============================================================================================
# What already comes back
# =============================================================================================


def test_the_collection_tree_comes_back(trip: Trip) -> None:
    assert_same(collection_tree, trip)
    actual = collection_tree(trip.source)
    expected = ["Reading list", "Reviews", "Reviews/2025", "Reviews/2025/Drafts"]
    assert actual == expected


def test_articles_come_back_identical_with_their_collections(trip: Trip) -> None:
    assert_same(articles, trip)


def test_stored_files_come_back_byte_identical_under_the_same_parent(trip: Trip) -> None:
    assert_same(stored_files, trip)
    assert len(stored_files(trip.source)) > 3


# =============================================================================================
# What does not (live round trip on teststr, 2026-11-24)
# =============================================================================================


def test_a_child_whose_parent_was_not_restored_is_reported_not_dropped_silently(
    trip: Trip,
) -> None:
    notes = [w for w in trip.report.warnings if "images embedded in notes" in w]

    assert len(notes) == 1, "the note image is not restored yet, and the restore says so"
    assert trip.report.errors  # the annotations (#685) still fail, as before


def test_standalone_notes_and_files_are_not_duplicated_by_a_second_restore(trip: Trip) -> None:
    expected = (standalone_notes(trip.target.lib), standalone_files(trip.target.lib))

    again = trip.restore_again()

    actual = (standalone_notes(trip.target.lib), standalone_files(trip.target.lib))
    assert actual == expected
    assert again.items_skipped_existing >= 1


def test_a_dry_run_counts_the_standalone_note_as_an_item(trip: Trip, tmp_path: Path) -> None:
    empty = FakeTarget("9999")
    repository: Any = cast(Any, empty)

    plan = RestoreService(repository, repository, repository, repository).restore_archive(
        str(trip.archive), dry_run=True
    )

    assert plan.items_created >= len(standalone_notes(trip.source)) + 1
    assert not empty.lib.items, "a dry run writes nothing"


def test_a_second_restore_adds_nothing(trip: Trip) -> None:
    """Live items, collections and files; the trash has its own check (#683)."""
    before = (len(trip.target.lib.live_items()), len(trip.target.lib.collections))

    again = trip.restore_again()

    expected = before
    actual = (len(trip.target.lib.live_items()), len(trip.target.lib.collections))
    assert actual == expected
    created = (again.collections_created, again.attachments_uploaded)
    nothing = (0, 0)
    assert created == nothing


def test_a_partly_restored_library_gets_only_what_is_missing(trip: Trip) -> None:
    """Remove a collection and a file; a second restore puts back those and nothing else."""
    lib = trip.target.lib
    drafts = next(k for k in lib.collections if col_path(lib, k) == "Reviews/2025/Drafts")
    del lib.collections[drafts]
    pdf = next(
        k
        for k, r in lib.items.items()
        if r["data"]["itemType"] == "attachment" and r["data"].get("parentItem")
    )
    del lib.items[pdf]
    items_before = len(lib.live_items())

    again = trip.restore_again()

    assert again.collections_created == 1
    assert again.attachments_uploaded == 1
    assert len(lib.live_items()) == items_before + 1
    assert drafts not in lib.collections, "a new key, not the deleted one"


def test_a_dry_run_of_a_second_restore_reports_the_same_nothing(trip: Trip) -> None:
    service = RestoreService(
        *[cast(Any, trip.target)] * 4  # type: ignore[arg-type]
    )

    plan = service.restore_archive(str(trip.archive), dry_run=True)

    assert plan.collections_created == 0
    assert plan.attachments_uploaded == 0
    assert plan.attachments_skipped_existing > 0


def test_standalone_notes_and_files_come_back_in_their_collections(trip: Trip) -> None:
    assert_same(standalone_notes, trip)
    assert_same(standalone_files, trip)


@finding(682, "create_note sends only the text: the note's tags are never sent")
def test_note_tags_come_back(trip: Trip) -> None:
    assert_same(note_tags, trip)


@finding(683, "create_note cannot say `deleted`: trashed notes come back live")
def test_trashed_items_come_back_trashed(trip: Trip) -> None:
    assert_same(trash_state, trip)


@finding(
    684, "the attachment is named after the temp file; title, url, dates and link mode are lost"
)
def test_attachments_keep_their_metadata(trip: Trip) -> None:
    assert_same(attachments, trip)


@finding(685, "annotations are created as top-level items with the old parent key (HTTP 409)")
def test_annotations_come_back_under_their_pdf(trip: Trip) -> None:
    assert_same(annotations, trip)
    errors = trip.report.errors
    no_errors: List[str] = []
    assert errors == no_errors


@finding(686, "relations are copied with the old item URIs")
def test_related_items_stay_related(trip: Trip) -> None:
    assert_same(relations, trip)
    assert len(relations(trip.source)) > 1


@finding(687, "dateAdded and dateModified are removed from the payload")
def test_dates_are_kept(trip: Trip) -> None:
    assert_same(dates, trip)
