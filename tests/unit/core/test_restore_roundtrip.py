"""A backup restored into an empty library must give back the library (tracking issue #679).

The sample library of `tests/zotero_fake.py` (nested collections, articles, notes with tags,
a standalone note and file, snapshots, annotated PDFs, related items, dates, a trash) is backed
up with `--trash` through the real client against the fake Web API, then restored through the
real `RestoreService` into a `FakeTarget`, which answers the repository calls the way the Web
API does. Keys change on a restore, so source and target are compared through views that do not
use them: collections by path, items by their own fields and their parent's title.

The suite began as the findings of a live round trip on the `teststr` group (2026-11-24), each
recorded here as a strict `xfail` and fixed one by one (tracking issue #679); none is left. They
are listed so a regression can be traced:

#680 a second restore duplicated the collections and re-uploaded the attachments
#681 notes and files without a parent item were dropped
#682 notes lost their tags
#683 trashed items came back live
#684 attachments were named after the temp file and lost title, URL, dates and link mode
#685 annotations were rejected (HTTP 409)
#686 related-item links kept the old item keys
#687 dates added and modified were replaced by the restore date
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import pytest

from tests.zotero_fake import GROUP, FakeLibrary, FakeTarget, FakeZoteroServer, populate
from zotero_cli.core.models import LibraryRef
from zotero_cli.core.services.restore_service import RestoreReport, RestoreService
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.infra.zotero_api import ZoteroAPIClient

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
    # Tags with both types, on a child note and on a stand-alone one
    source.add_item(
        "TAGNOTE1",
        "note",
        parent="BOOK0001",
        note="<p>two kinds of tag</p>",
        tags=[{"tag": "manual", "type": 0}, {"tag": "automatic", "type": 1}],
    )
    source.items["NOTE0001"]["data"]["tags"] = [{"tag": "stand-alone-tag"}]
    # A link to an item of another library: nothing of this archive's to rewrite
    source.items["UNIC0001"]["data"]["relations"] = {
        "owl:sameAs": ["http://zotero.org/groups/9999/items/OTHERLIB"]
    }
    # A file trashed on its own, and a stand-alone note in the trash
    source.add_item(
        "TRSHFIL1",
        "attachment",
        parent="BOOK0001",
        linkMode="imported_file",
        filename="trashed.pdf",
        contentType="application/pdf",
        file=b"%PDF-1.7 trashed on its own",
        deleted=True,
    )
    source.add_item(
        "TRSHNTE2",
        "note",
        collections=["COLB0001"],
        note="<p>stand-alone, trashed</p>",
        deleted=True,
    )
    # The same paper filed twice, each copy in its own collection with its own files, notes and
    # annotations (the live group had three such pairs, Issue #699)
    for suffix, collection in (("A", "COLA0001"), ("B", "COLB0001")):
        copy_key = f"DUP{suffix}0001"
        source.add_item(
            copy_key,
            "journalArticle",
            collections=[collection],
            title="The same paper twice",
            DOI="10.1/duplicated",
            url="https://example.org/paper",
        )
        source.add_item(
            f"DUP{suffix}PDF1",
            "attachment",
            parent=copy_key,
            linkMode="imported_file",
            filename=f"copy-{suffix}.pdf",
            title="Full Text PDF",
            contentType="application/pdf",
            file=b"%PDF-1.7 copy " + suffix.encode(),
        )
        source.add_item(
            f"DUP{suffix}NTE1", "note", parent=copy_key, note=f"<p>note of copy {suffix}</p>"
        )
        source.add_item(
            f"DUP{suffix}ANN1",
            "annotation",
            parent=f"DUP{suffix}PDF1",
            annotationType="highlight",
            annotationText=f"text {suffix}",
            annotationPosition=f'{{"pageIndex":{ord(suffix)}}}',
        )
    # Saved searches: one that refers to another (listed first), one filed by collection, one that
    # names a collection that is gone (Issue #678)
    source.searches["SRCH0011"] = {
        "key": "SRCH0011",
        "version": 3,
        "data": {
            "key": "SRCH0011",
            "name": "Refers to the first",
            "conditions": [
                {"condition": "savedSearch", "operator": "is", "value": "SRCH0010"},
                {"condition": "title", "operator": "contains", "value": "paper"},
            ],
        },
    }
    source.searches["SRCH0010"] = {
        "key": "SRCH0010",
        "version": 2,
        "data": {
            "key": "SRCH0010",
            "name": "In Reviews, to read",
            "conditions": [
                {"condition": "collection", "operator": "is", "value": "COLA0001"},
                {"condition": "tag", "operator": "is", "value": "to-read"},
            ],
        },
    }
    source.searches["SRCH0012"] = {
        "key": "SRCH0012",
        "version": 4,
        "data": {
            "key": "SRCH0012",
            "name": "Names a collection that is gone",
            "conditions": [{"condition": "collection", "operator": "is", "value": "GHOSTCOL"}],
        },
    }
    archive = tmp_path / "library.zaf"
    GatewayFactory.get_backup_service(client).backup_system(str(archive), include_trash=True)
    target = FakeTarget()

    def restore() -> RestoreReport:
        repository: Any = cast(Any, target)
        here = LibraryRef(target.lib.library_type, target.lib.library_id)
        service = RestoreService(repository, repository, repository, repository, library=here)
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


def visible(lib: FakeLibrary) -> List[Dict[str, Any]]:
    """The items Zotero shows: not in the trash, directly or through their parent."""
    return [r for r in lib.live_items() if not lib.is_trashed(r["key"])]


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


def note_text(lib: FakeLibrary, raw: Dict[str, Any]) -> str:
    """A note's text with each embedded image's key replaced by what the image is (its hash), so
    two libraries can be compared although their keys differ (Issue #704)."""
    import hashlib

    def image(match: "re.Match[str]") -> str:
        key = match.group(1)
        digest = hashlib.sha256(lib.files[key]).hexdigest()[:12] if key in lib.files else "MISSING"
        return f'data-attachment-key="image:{digest}"'

    return re.sub(r'data-attachment-key="([A-Z0-9]{8})"', image, raw["data"]["note"])


def note_images(lib: FakeLibrary) -> List[str]:
    """Each embedded image: the note it is under (by its text), its type and its hash."""
    import hashlib

    return sorted(
        dump(
            (
                note_text(lib, lib.items[r["data"]["parentItem"]]),
                r["data"].get("contentType"),
                hashlib.sha256(lib.files[k]).hexdigest(),
            )
        )
        for k, r in lib.items.items()
        if r["data"].get("linkMode") == "embedded_image"
    )


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
        dump((note_text(lib, r), r["data"].get("tags", []), paths(lib, r["data"])))
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
            (ident(lib, r["data"].get("parentItem")), note_text(lib, r), r["data"].get("tags", []))
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


def trashed_files(lib: FakeLibrary) -> List[str]:
    """For every stored file: its hash, and whether the attachment is in the trash."""
    import hashlib

    return sorted(
        dump((hashlib.sha256(lib.files[k]).hexdigest(), lib.is_trashed(k)))
        for k, r in lib.items.items()
        if r["data"]["itemType"] == "attachment"
        and k in lib.files
        and r["data"].get("linkMode") != "embedded_image"
    )


def trashed_standalone_notes(lib: FakeLibrary) -> List[str]:
    return sorted(
        dump((r["data"]["note"], lib.is_trashed(k)))
        for k, r in lib.items.items()
        if r["data"]["itemType"] == "note" and "parentItem" not in r["data"]
    )


def attachments(lib: FakeLibrary) -> List[str]:
    import hashlib

    fields = ("title", "filename", "linkMode", "url", "accessDate", "contentType", "tags", "path")
    found = []
    for key, raw in lib.items.items():
        d = raw["data"]
        if d["itemType"] != "attachment" or d.get("linkMode") == "embedded_image":
            continue
        record: Dict[str, Any] = {f: d.get(f) for f in fields}
        record["title"] = d.get("title") or ""  # the API answers "" for an attachment without one
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


def searches(lib: FakeLibrary) -> List[str]:
    """Each saved search by name, its conditions with collections shown by path and referenced
    searches by name; the one that names a missing collection is not expected back."""
    names = {k: s["data"]["name"] for k, s in lib.searches.items()}
    found = []
    for search in lib.searches.values():
        conditions = []
        for c in search["data"].get("conditions", []):
            value = c.get("value")
            if c.get("condition") == "collection":
                value = col_path(lib, value) or f"UNRESOLVED:{value}"
            elif c.get("condition") == "savedSearch":
                value = names.get(value, f"UNRESOLVED:{value}")
            conditions.append((c.get("condition"), c.get("operator"), value))
        if not any(str(v).startswith("UNRESOLVED") for _, _, v in conditions):
            found.append(dump((search["data"]["name"], conditions)))
    return sorted(found)


def dates(lib: FakeLibrary) -> List[str]:
    return sorted(
        dump((ident(lib, k), r["data"].get("dateAdded"), r["data"].get("dateModified")))
        for k, r in lib.items.items()
        if r["data"]["itemType"]
        in ("journalArticle", "book", "thesis", "note", "attachment", "annotation")
        and r["data"].get("linkMode") != "embedded_image"  # not restored yet: a warning
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


def test_images_embedded_in_notes_come_back_under_their_note(trip: Trip) -> None:
    """Issue #704."""
    assert_same(note_images, trip)
    assert len(note_images(trip.source)) == 1
    assert not [w for w in trip.report.warnings if "embedded" in w]
    assert trip.report.errors == []


def test_a_restored_note_points_at_the_new_key_of_its_image(trip: Trip) -> None:
    lib = trip.target.lib
    note = next(r for r in lib.items.values() if "data-attachment-key" in r["data"].get("note", ""))
    image = next(r for r in lib.items.values() if r["data"].get("linkMode") == "embedded_image")

    assert f'data-attachment-key="{image["key"]}"' in note["data"]["note"]
    assert image["key"] != "EMB00001"
    assert image["data"]["parentItem"] == note["key"]


def test_a_second_restore_does_not_duplicate_notes_with_images_or_their_images(
    trip: Trip,
) -> None:
    before = (note_images(trip.target.lib), note_tags(trip.target.lib))

    again = trip.restore_again()

    assert (note_images(trip.target.lib), note_tags(trip.target.lib)) == before
    assert again.attachments_uploaded == 0
    assert again.errors == []


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


def test_a_linked_file_cannot_go_into_a_group_library_and_that_is_a_warning(trip: Trip) -> None:
    """The Web API: "Linked files can only be added to user libraries" (checked live)."""
    group = FakeTarget("9999", "group")
    repository: Any = cast(Any, group)

    report = RestoreService(repository, repository, repository, repository).restore_archive(
        str(trip.archive)
    )

    assert any("linked files in personal libraries" in w for w in report.warnings)
    assert not [e for e in report.errors if "attachment" in e]
    assert not [r for r in group.lib.items.values() if r["data"].get("linkMode") == "linked_file"]
    assert [r for r in group.lib.items.values() if r["data"].get("linkMode") == "linked_url"]


def test_saved_searches_come_back_with_their_collections_and_searches_remapped(trip: Trip) -> None:
    """Issue #678: a condition names a collection or a search by key, and the keys are new."""
    assert_same(searches, trip)
    expected = searches(trip.source)
    assert len(expected) == 3  # the one that was already in the sample, and the two new ones


def test_a_search_listed_before_the_one_it_refers_to_is_created_after_it(trip: Trip) -> None:
    lib = trip.target.lib
    by_name = {s["data"]["name"]: s for s in lib.searches.values()}
    first = by_name["In Reviews, to read"]["key"]

    refers = by_name["Refers to the first"]["data"]["conditions"][0]

    assert refers == {"condition": "savedSearch", "operator": "is", "value": first}
    assert first in lib.searches


def test_a_search_naming_a_missing_collection_is_skipped_and_said(trip: Trip) -> None:
    names = [s["data"]["name"] for s in trip.target.lib.searches.values()]

    assert "Names a collection that is gone" not in names
    assert any(
        "Names a collection that is gone" in w and "GHOSTCOL" in w for w in trip.report.warnings
    )
    assert trip.report.errors == []


def test_the_report_counts_the_saved_searches(trip: Trip) -> None:
    assert trip.report.searches_created == 3
    assert trip.report.searches_skipped_existing == 0


def test_a_second_restore_does_not_duplicate_the_saved_searches(trip: Trip) -> None:
    before = len(trip.target.lib.searches)

    again = trip.restore_again()

    assert len(trip.target.lib.searches) == before
    assert again.searches_created == 0
    assert again.searches_skipped_existing == 3


def test_a_dry_run_counts_the_saved_searches_and_writes_none(trip: Trip) -> None:
    empty = FakeTarget("9999")
    repository: Any = cast(Any, empty)

    plan = RestoreService(
        repository, repository, repository, repository, library=LibraryRef("user", "9999")
    ).restore_archive(str(trip.archive), dry_run=True)

    assert plan.searches_created == 3
    assert not empty.lib.searches


def test_a_second_restore_adds_nothing(trip: Trip) -> None:
    """Everything, the trash included."""
    before = (len(trip.target.lib.items), len(trip.target.lib.collections))

    again = trip.restore_again()

    expected = before
    actual = (len(trip.target.lib.items), len(trip.target.lib.collections))
    assert actual == expected
    created = (again.collections_created, again.attachments_uploaded)
    nothing = (0, 0)
    assert created == nothing


def test_two_copies_of_one_paper_stay_two_copies_with_their_own_children(trip: Trip) -> None:
    """Issue #699: same title and DOI, told apart by their collections."""
    lib = trip.target.lib
    copies = [r for r in lib.items.values() if r["data"].get("title") == "The same paper twice"]

    assert len(copies) == 2
    for copy in copies:
        kids = [r["data"] for r in lib.items.values() if r["data"].get("parentItem") == copy["key"]]
        where = col_path(lib, copy["data"]["collections"][0])
        suffix = "A" if where == "Reviews" else "B"
        assert sorted(k["itemType"] for k in kids) == ["attachment", "note"]
        assert {k["filename"] for k in kids if k["itemType"] == "attachment"} == {
            f"copy-{suffix}.pdf"
        }
        assert {k["note"] for k in kids if k["itemType"] == "note"} == {
            f"<p>note of copy {suffix}</p>"
        }


def test_a_library_that_has_only_one_of_two_copies_gets_the_other(trip: Trip) -> None:
    lib = trip.target.lib
    gone = next(
        k
        for k, r in lib.items.items()
        if r["data"].get("title") == "The same paper twice"
        and col_path(lib, r["data"]["collections"][0]) == "Reading list"
    )
    removed = [k for k, r in lib.items.items() if r["data"].get("parentItem") == gone]
    for key in removed:
        for sub in [k for k, r in lib.items.items() if r["data"].get("parentItem") == key]:
            del lib.items[sub]  # the annotations of the PDF go with it
        del lib.items[key]
    del lib.items[gone]
    before = len(lib.items)

    again = trip.restore_again()

    copies = [r for r in lib.items.values() if r["data"].get("title") == "The same paper twice"]
    assert len(copies) == 2
    assert len(lib.items) > before
    assert again.items_created >= 1


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
    annotations_of_it = [k for k, r in lib.items.items() if r["data"].get("parentItem") == pdf]
    for key in annotations_of_it:
        del lib.items[key]  # its annotations go with it, as in Zotero
    del lib.items[pdf]
    items_before = len(visible(lib))

    again = trip.restore_again()

    assert again.collections_created == 1
    assert again.attachments_uploaded == 1
    assert len(visible(lib)) == items_before + 1 + len(annotations_of_it)
    assert annotations_of_it, "the PDF had annotations and they came back with it"
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


def test_note_tags_come_back(trip: Trip) -> None:
    assert_same(note_tags, trip)
    assert any("automatic" in line for line in note_tags(trip.target.lib)), "with their types"


def test_trashed_items_come_back_trashed(trip: Trip) -> None:
    assert_same(trash_state, trip)
    assert_same(trashed_files, trip)
    assert_same(trashed_standalone_notes, trip)
    assert any("true" in line for line in trash_state(trip.target.lib))
    # the trashed article, a note, a file and a stand-alone note (the note under the trashed
    # article is not flagged itself: it is in the trash through its parent)
    trashed_count = trip.report.items_trashed
    assert trashed_count == 4


def test_attachments_keep_their_metadata(trip: Trip) -> None:
    assert_same(attachments, trip)


def test_annotations_come_back_under_their_pdf(trip: Trip) -> None:
    assert_same(annotations, trip)
    errors = trip.report.errors
    no_errors: List[str] = []
    assert errors == no_errors


def test_related_items_stay_related(trip: Trip) -> None:
    assert_same(relations, trip)
    assert len(relations(trip.source)) > 1


def test_relations_point_at_the_target_library_and_its_new_keys(trip: Trip) -> None:
    target = trip.target.lib
    ours = [
        uri
        for raw in target.items.values()
        for uris in raw["data"].get("relations", {}).values()
        for uri in uris
        if "OTHERLIB" not in uri
    ]

    assert ours, "the articles are related"
    for uri in ours:
        assert uri.startswith("http://zotero.org/users/8888/items/")
        assert uri.rsplit("/", 1)[-1] in target.items
    assert trip.report.relations_restored >= 2


def test_a_link_to_another_librarys_item_is_kept_as_it_was(trip: Trip) -> None:
    target = trip.target.lib
    book = next(r for r in target.items.values() if r["data"].get("title", "").startswith("Ação"))

    assert book["data"]["relations"] == {
        "owl:sameAs": ["http://zotero.org/groups/9999/items/OTHERLIB"]
    }


def test_a_link_to_an_item_the_archive_does_not_hold_is_dropped_and_said(
    trip: Trip, tmp_path: Path
) -> None:
    """Never rewritten to a wrong item: the link goes, the warning stays."""
    trip.source.items["JRN00001"]["data"]["relations"]["dc:relation"].append(
        trip.source.item_uri("NOTINTHEARCHIVE")
    )
    server = FakeZoteroServer()
    server.register(trip.source)
    client = ZoteroAPIClient("key", trip.source.library_id, trip.source.library_type)
    client.http.session = server.session()  # type: ignore[assignment]
    archive = tmp_path / "again.zaf"
    GatewayFactory.get_backup_service(client).backup_system(str(archive), include_trash=True)
    target = FakeTarget("7777")
    repository: Any = cast(Any, target)
    here = LibraryRef("user", "7777")

    report = RestoreService(
        repository, repository, repository, repository, library=here
    ).restore_archive(str(archive))

    article = next(
        r for r in target.lib.items.values() if r["data"].get("title") == "A study of backups"
    )
    assert len(article["data"]["relations"]["dc:relation"]) == 1
    assert any("NOTINTHEARCHIVE" in w for w in report.warnings)


def test_a_second_restore_does_not_touch_the_relations_again(trip: Trip) -> None:
    again = trip.restore_again()

    assert again.relations_restored == 0


def test_a_dry_run_counts_the_relations_and_writes_nothing(trip: Trip) -> None:
    empty = FakeTarget("9999")
    repository: Any = cast(Any, empty)

    plan = RestoreService(
        repository, repository, repository, repository, library=LibraryRef("user", "9999")
    ).restore_archive(str(trip.archive), dry_run=True)

    assert plan.relations_restored >= 2
    assert not empty.lib.items


def test_dates_are_kept(trip: Trip) -> None:
    assert_same(dates, trip)
