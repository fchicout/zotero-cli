"""What a backup (.zaf) has to contain to restore a Zotero library without loss.

The tests run the real stack (CLI handlers, gateway factory, `ZoteroAPIClient`, `BackupService`,
`VerifyService`) against `tests/zotero_fake.py`, an in-memory Zotero Web API, for a user library
and for a group library. They describe the required behaviour:

- the whole library (or one collection) goes in: every collection with its hierarchy, every
  item, sub-item, note, annotation and attachment file, with the item relationships Zotero
  Desktop and the Web Library show (parent/child, collection membership, related items, tags);
- the archive says which library it came from and passes `system verify`;
- a backup that cannot be complete says so, and never destroys an earlier backup.

Tests that pass pin what already works. Tests marked `xfail(strict=True)` are DISCREPANCIES
between that behaviour and the code; each reason starts with an id (D1..D11) listed in the
report that came with this file. They are not bugs fixed here: when the code is corrected a
strict xfail turns into a failure, which is the cue to remove its marker.

D1  files of `imported_url` (web snapshots) and `embedded_image` attachments are not saved
D2  items in the trash are not saved
D3  the manifest does not record which library (user/group, id) the archive came from
D4  a collection backup has no collections.json (names, hierarchy are lost)
D5  a backup missing files still reports "Backup complete" and exits 0
D6  two attachments of one item with the same file name overwrite each other; archive fails verify
D7  a collection backup skips the items of its sub-collections
D8  a collection backup skips the annotations of the PDFs it contains
D9  saved searches are not saved
D10 no per-call parameter selects a group library (only the config file or `--user`)
D11 a failed run overwrites an earlier good backup at the same path with a partial archive
"""

import hashlib
import json
import os
import stat
import sys
import warnings
import zipfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest

from tests.zotero_fake import FakeLibrary, FakeZoteroServer
from zotero_cli.core.exceptions import PartialFailure, Unavailable
from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.services.verify_service import VerifyService
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.infra.http_client import ZoteroHttpClient
from zotero_cli.infra.zotero_api import ZoteroAPIClient


def discrepancy(ref: str, why: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{ref}: {why}")


# --- the library under test ------------------------------------------------------------------

USER = ("user", "42")
GROUP = ("group", "777")
PDF = b"%PDF-1.7 " + bytes(range(256)) * 20
SNAPSHOT = b"<html><body>saved page</body></html>"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

# Everything Zotero shows (not in the trash), by role.
LIVE_KEYS = {
    "COLLECTION_TREE": ["COLA0001", "COLA1001", "COLA1A01", "COLB0001"],
    "TOP": ["JRN00001", "BOOK0001", "NOTE0001", "STND0001", "UNFI0001", "UNIC0001"],
    "CHILDREN": [
        "PDF00001",
        "ANN00001",
        "ANN00002",
        "SNP00001",
        "LNK00001",
        "LFL00001",
        "NOT00001",
        "EMB00001",
        "BK1PDF01",
        "UNFN0001",
        "UNIC0002",
    ],
}
ALL_LIVE = LIVE_KEYS["TOP"] + LIVE_KEYS["CHILDREN"]


def populate(lib: FakeLibrary) -> FakeLibrary:
    """A library with every shape of item Zotero has: nested collections, an item in two
    collections, related items, PDFs with annotations, snapshots, links, linked files, notes with
    embedded images, stand-alone notes and files, unfiled items, Unicode, and trash."""
    lib.add_collection("COLA0001", "Reviews")
    lib.add_collection("COLA1001", "2025", parent="COLA0001")
    lib.add_collection("COLA1A01", "Drafts", parent="COLA1001")
    lib.add_collection("COLB0001", "Reading list")

    lib.add_item(
        "JRN00001",
        "journalArticle",
        collections=["COLA0001", "COLB0001"],
        title="A study of backups",
        creators=[
            {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"},
            {"creatorType": "editor", "name": "The Committee"},
        ],
        abstractNote="Everything must be kept.",
        DOI="10.1000/backup.1",
        date="2025-06-01",
        extra="arXiv: 2501.00001",
        tags=[{"tag": "to-read", "type": 0}, {"tag": "auto", "type": 1}],
        relations={"dc:relation": [lib.item_uri("BOOK0001")]},
    )
    lib.add_item(
        "PDF00001",
        "attachment",
        parent="JRN00001",
        linkMode="imported_file",
        filename="study.pdf",
        title="Full text",
        contentType="application/pdf",
        file=PDF,
    )
    lib.add_item(
        "ANN00001", "annotation", parent="PDF00001", annotationType="highlight", annotationText="x"
    )
    lib.add_item(
        "ANN00002", "annotation", parent="PDF00001", annotationType="note", annotationComment="y"
    )
    lib.add_item(
        "SNP00001",
        "attachment",
        parent="JRN00001",
        linkMode="imported_url",
        filename="snapshot.html",
        url="https://example.org/paper",
        contentType="text/html",
        file=SNAPSHOT,
    )
    lib.add_item(
        "LNK00001",
        "attachment",
        parent="JRN00001",
        linkMode="linked_url",
        title="Publisher page",
        url="https://example.org/paper",
    )
    lib.add_item(
        "LFL00001",
        "attachment",
        parent="JRN00001",
        linkMode="linked_file",
        filename="local.pdf",
        path="/home/someone/papers/local.pdf",
    )
    lib.add_item(
        "NOT00001",
        "note",
        parent="JRN00001",
        note='<p>Read this</p><img data-attachment-key="EMB00001"/>',
        tags=[{"tag": "note-tag"}],
    )
    lib.add_item(
        "EMB00001",
        "attachment",
        parent="NOT00001",
        linkMode="embedded_image",
        contentType="image/png",
        file=PNG,
    )

    lib.add_item(
        "BOOK0001",
        "book",
        collections=["COLA1A01"],
        title="The book",
        relations={"dc:relation": [lib.item_uri("JRN00001")]},
    )
    lib.add_item(
        "BK1PDF01",
        "attachment",
        parent="BOOK0001",
        linkMode="imported_file",
        filename="book.pdf",
        contentType="application/pdf",
        file=PDF + b"book",
    )
    lib.add_item("NOTE0001", "note", collections=["COLA1001"], note="<p>stand-alone note</p>")
    lib.add_item(
        "STND0001",
        "attachment",
        collections=["COLA0001"],
        linkMode="imported_file",
        filename="loose.pdf",
        contentType="application/pdf",
        file=PDF + b"loose",
    )
    lib.add_item("UNFI0001", "thesis", title="Unfiled thesis")
    lib.add_item("UNFN0001", "note", parent="UNFI0001", note="<p>child of an unfiled item</p>")
    lib.add_item("UNIC0001", "book", collections=["COLB0001"], title="Ação & relatório – 研究")
    lib.add_item(
        "UNIC0002",
        "attachment",
        parent="UNIC0001",
        linkMode="imported_file",
        filename="relatório ação.pdf",
        contentType="application/pdf",
        file=PDF + b"unicode",
    )

    lib.add_item("TRSH0001", "book", collections=["COLA0001"], title="Deleted book", deleted=True)
    lib.add_item("TRSHN001", "note", parent="TRSH0001", note="<p>in the trash</p>")
    lib.searches["SRCH0001"] = {
        "key": "SRCH0001",
        "version": 5,
        "data": {"key": "SRCH0001", "name": "Unread", "conditions": [{"condition": "tag"}]},
    }
    return lib


@dataclass
class World:
    server: FakeZoteroServer
    lib: FakeLibrary  # the library the backup targets
    other: FakeLibrary  # the account's other library: it must never be read
    service: BackupService


@pytest.fixture(autouse=True)
def _no_retry_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 5xx makes the client retry with seconds of back-off: not in a unit test."""
    monkeypatch.setattr(ZoteroHttpClient._get_with_retries.retry, "sleep", lambda _s: None)  # type: ignore[attr-defined]


def _server() -> FakeZoteroServer:
    server = FakeZoteroServer()
    server.register(populate(FakeLibrary(*USER, name="My Library")))
    server.register(populate(FakeLibrary(*GROUP, name="Lab Group")))
    return server


@pytest.fixture(params=[USER, GROUP], ids=["user-library", "group-library"])
def world(request: pytest.FixtureRequest) -> World:
    server = _server()
    target = server.libraries[request.param]
    other = server.libraries[GROUP if request.param == USER else USER]
    client = ZoteroAPIClient("key", target.library_id, target.library_type)
    client.http.session = server.session()  # type: ignore[assignment]
    return World(server, target, other, GatewayFactory.get_backup_service(client))


# --- reading an archive back, independently of the code that wrote it -------------------------


class Archive:
    def __init__(self, source: "bytes | Path | str") -> None:
        self.zf = zipfile.ZipFile(BytesIO(source) if isinstance(source, bytes) else source)
        self.names = self.zf.namelist()
        self.manifest: Dict[str, Any] = json.loads(self.zf.read("manifest.json"))
        self.data: List[Dict[str, Any]] = json.loads(self.zf.read("data.json"))
        self.by_key = {d["key"]: d for d in self.data}
        self.collections: Optional[List[Dict[str, Any]]] = (
            json.loads(self.zf.read("collections.json"))
            if "collections.json" in self.names
            else None
        )
        self.errors = self.zf.read("errors.log").decode() if "errors.log" in self.names else ""

    @property
    def keys(self) -> List[str]:
        return [d["key"] for d in self.data]

    def file_of(self, key: str) -> bytes:
        return self.zf.read(self.manifest["file_map"][key]["path"])


def backup_system(world: World) -> Archive:
    out = BytesIO()
    world.service.backup_system(out)
    return Archive(out.getvalue())


def backup_collection(world: World, key: str) -> Archive:
    out = BytesIO()
    world.service.backup_collection(key, out)
    return Archive(out.getvalue())


# =============================================================================================
# 1. Full library backup: nothing is left out, nothing is altered
# =============================================================================================


def test_library_backup_has_every_item_exactly_once(world: World) -> None:
    archive = backup_system(world)

    assert sorted(archive.keys) == sorted(ALL_LIVE)
    assert len(archive.keys) == len(set(archive.keys)), "an item was written twice"


def test_library_backup_keeps_every_item_exactly_as_zotero_returned_it(world: World) -> None:
    """Version, dates, library stub, links, meta and all fields: restore may need any of them."""
    archive = backup_system(world)

    for key in ALL_LIVE:
        assert archive.by_key[key] == world.lib.items[key], key


def test_the_whole_item_tree_is_kept(world: World) -> None:
    """Sub-items point to their parents, and every parent is in the archive: PDF -> annotation,
    article -> attachments and notes, note -> embedded image."""
    archive = backup_system(world)

    parents = {
        "PDF00001": "JRN00001",
        "ANN00001": "PDF00001",
        "ANN00002": "PDF00001",
        "SNP00001": "JRN00001",
        "LNK00001": "JRN00001",
        "LFL00001": "JRN00001",
        "NOT00001": "JRN00001",
        "EMB00001": "NOT00001",
        "BK1PDF01": "BOOK0001",
        "UNFN0001": "UNFI0001",
        "UNIC0002": "UNIC0001",
    }
    for child, parent in parents.items():
        assert archive.by_key[child]["data"]["parentItem"] == parent, child
    orphans = [
        item["key"]
        for item in archive.data
        if "parentItem" in item["data"] and item["data"]["parentItem"] not in archive.by_key
    ]
    assert orphans == [], "items whose parent is not in the archive"
    for top in ("NOTE0001", "STND0001", "UNFI0001"):
        assert "parentItem" not in archive.by_key[top]["data"], f"{top} must stay top-level"


def test_every_collection_is_kept_with_its_hierarchy(world: World) -> None:
    archive = backup_system(world)

    assert archive.collections is not None
    by_key = {c["key"]: c for c in archive.collections}
    assert sorted(by_key) == sorted(LIVE_KEYS["COLLECTION_TREE"])
    assert by_key["COLA0001"]["data"]["name"] == "Reviews"
    assert not by_key["COLA0001"]["data"]["parentCollection"]
    assert by_key["COLA1001"]["data"]["parentCollection"] == "COLA0001"
    assert by_key["COLA1A01"]["data"]["parentCollection"] == "COLA1001"
    assert by_key["COLA1A01"]["data"]["name"] == "Drafts"
    assert not by_key["COLB0001"]["data"]["parentCollection"]


def test_collection_membership_is_kept_and_every_collection_it_names_is_archived(
    world: World,
) -> None:
    """An item filed in two collections stays in both; unfiled stays unfiled; and no item names a
    collection the archive lacks (a restore could not place it)."""
    archive = backup_system(world)

    assert archive.collections is not None
    known = {c["key"] for c in archive.collections}
    assert archive.by_key["JRN00001"]["data"]["collections"] == ["COLA0001", "COLB0001"]
    assert archive.by_key["BOOK0001"]["data"]["collections"] == ["COLA1A01"]
    assert archive.by_key["UNFI0001"]["data"]["collections"] == []
    for item in archive.data:
        assert set(item["data"].get("collections", [])) <= known, item["key"]


def test_tags_creators_relations_and_text_fields_survive(world: World) -> None:
    archive = backup_system(world)

    article = archive.by_key["JRN00001"]["data"]
    assert article["tags"] == [{"tag": "to-read", "type": 0}, {"tag": "auto", "type": 1}]
    assert article["creators"][0] == {
        "creatorType": "author",
        "firstName": "Ada",
        "lastName": "Lovelace",
    }
    assert article["creators"][1] == {"creatorType": "editor", "name": "The Committee"}
    assert (article["abstractNote"], article["DOI"], article["date"]) == (
        "Everything must be kept.",
        "10.1000/backup.1",
        "2025-06-01",
    )
    assert article["extra"] == "arXiv: 2501.00001"
    assert archive.by_key["NOT00001"]["data"]["tags"] == [{"tag": "note-tag"}]
    assert archive.by_key["NOT00001"]["data"]["note"].startswith("<p>Read this</p>")


def test_related_items_point_at_items_that_are_in_the_archive(world: World) -> None:
    """`dc:relation` links items inside one library by URI; both ends must be archived."""
    archive = backup_system(world)

    related = archive.by_key["JRN00001"]["data"]["relations"]["dc:relation"]
    assert related == [world.lib.item_uri("BOOK0001")]
    for item in archive.data:
        for uris in item["data"].get("relations", {}).values():
            for uri in [uris] if isinstance(uris, str) else uris:
                assert uri.rsplit("/", 1)[-1] in archive.by_key, f"{item['key']} -> {uri}"


def test_attachment_files_are_byte_identical_and_checksummed(world: World) -> None:
    archive = backup_system(world)

    stored = {"PDF00001", "BK1PDF01", "STND0001", "UNIC0002"}
    assert stored <= set(archive.manifest["file_map"])
    for key in stored:
        assert archive.file_of(key) == world.lib.files[key], key
        entry = archive.manifest["file_map"][key]
        assert entry["checksum"] == hashlib.sha256(world.lib.files[key]).hexdigest()


def test_stand_alone_files_and_unicode_names_are_kept(world: World) -> None:
    archive = backup_system(world)

    assert archive.file_of("STND0001") == PDF + b"loose"
    assert archive.by_key["UNIC0001"]["data"]["title"] == "Ação & relatório – 研究"
    assert archive.by_key["UNIC0002"]["data"]["filename"] == "relatório ação.pdf"
    assert archive.file_of("UNIC0002") == PDF + b"unicode"


def test_links_and_linked_files_keep_their_metadata_without_a_file(world: World) -> None:
    """A web link has no file at all. A linked file lives on the user's disk, which the Web API
    cannot serve: its record (path included) is kept and the missing file is logged."""
    archive = backup_system(world)

    assert archive.by_key["LNK00001"]["data"]["url"] == "https://example.org/paper"
    assert archive.by_key["LFL00001"]["data"]["path"] == "/home/someone/papers/local.pdf"
    assert "LNK00001" not in archive.manifest["file_map"]
    assert "LFL00001" not in archive.manifest["file_map"]
    assert "LFL00001" in archive.errors
    assert "LNK00001" not in archive.errors


def test_manifest_describes_a_library_archive(world: World) -> None:
    manifest = backup_system(world).manifest

    assert manifest["format"] == "zaf"
    assert manifest["scope_type"] == "library"
    assert manifest["generator"] == "zotero-cli"
    assert manifest["version"]
    assert datetime.fromisoformat(manifest["timestamp"]).utcoffset().total_seconds() == 0  # type: ignore[union-attr]
    assert "root_collection_key" not in manifest


def test_the_archive_passes_verification(world: World, tmp_path: Path) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))

    report = VerifyService().verify_archive(str(path))

    assert report.is_valid, report.errors
    assert report.item_count == len(ALL_LIVE)
    assert report.collection_count == len(LIVE_KEYS["COLLECTION_TREE"])
    assert report.file_count >= 4  # PDF, book PDF, stand-alone PDF, Unicode PDF (+ D1 files)


def test_verification_catches_a_damaged_attachment(world: World, tmp_path: Path) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))
    target = Archive(path).manifest["file_map"]["PDF00001"]["path"]
    damaged = tmp_path / "damaged.zaf"
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(damaged, "w") as dst:
        for info in src.infolist():
            content = src.read(info.filename)
            dst.writestr(info.filename, content[:-1] + b"X" if info.filename == target else content)

    report = VerifyService().verify_archive(str(damaged))

    assert not report.is_valid
    assert any("Checksum mismatch" in e for e in report.errors)


def test_two_backups_of_an_unchanged_library_hold_the_same_data(world: World) -> None:
    first, second = backup_system(world), backup_system(world)

    assert first.data == second.data
    assert first.collections == second.collections
    assert first.manifest["file_map"] == second.manifest["file_map"]


def test_an_empty_library_gives_a_valid_archive(tmp_path: Path) -> None:
    server = FakeZoteroServer()
    lib = server.register(FakeLibrary(*GROUP))
    client = ZoteroAPIClient("key", lib.library_id, lib.library_type)
    client.http.session = server.session()  # type: ignore[assignment]
    path = tmp_path / "empty.zaf"

    GatewayFactory.get_backup_service(client).backup_system(str(path))

    archive = Archive(path)
    assert archive.data == []
    assert archive.collections == []
    assert VerifyService().verify_archive(str(path)).is_valid


def test_a_library_larger_than_one_page_is_complete() -> None:
    """The Web API pages at 100: 250 articles with a note each is 500 items over 5+ pages."""
    server = FakeZoteroServer()
    lib = server.register(FakeLibrary(*GROUP))
    lib.add_collection("COLBIG01", "Big")
    for i in range(250):
        lib.add_item(f"ART{i:05d}", "journalArticle", collections=["COLBIG01"], title=f"t{i}")
        lib.add_item(f"NTE{i:05d}", "note", parent=f"ART{i:05d}", note=f"n{i}")
    client = ZoteroAPIClient("key", lib.library_id, lib.library_type)
    client.http.session = server.session()  # type: ignore[assignment]
    out = BytesIO()

    GatewayFactory.get_backup_service(client).backup_system(out)

    archive = Archive(out.getvalue())
    assert sorted(archive.keys) == sorted(lib.items)


# =============================================================================================
# 2. Choosing the library: user or group, and never the other one
# =============================================================================================


def test_a_backup_reads_only_the_selected_library(world: World) -> None:
    backup_system(world)

    assert world.lib.requests, "the selected library was not read"
    assert world.other.requests == [], "the account's other library was touched"


def test_a_backup_holds_items_of_the_selected_library_only(world: World) -> None:
    archive = backup_system(world)

    libraries = {(i["library"]["type"], str(i["library"]["id"])) for i in archive.data}
    assert libraries == {(world.lib.library_type, world.lib.library_id)}


# =============================================================================================
# 3. Collection backup
# =============================================================================================


def test_a_collection_backup_has_the_collection_items_and_their_sub_items(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    assert {"JRN00001", "STND0001"} <= set(archive.keys)
    assert {"PDF00001", "SNP00001", "LNK00001", "LFL00001", "NOT00001"} <= set(archive.keys)
    assert "TRSH0001" not in archive.keys
    assert "UNFI0001" not in archive.keys
    assert "COLB0001" not in archive.keys
    assert archive.file_of("PDF00001") == PDF
    assert archive.file_of("STND0001") == PDF + b"loose"


def test_a_collection_backup_names_its_collection_and_keeps_item_membership(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    assert archive.manifest["scope_type"] == "collection"
    assert archive.manifest["root_collection_key"] == "COLA0001"
    assert archive.manifest["root_collection_name"] == "Reviews"
    assert archive.by_key["JRN00001"]["data"]["collections"] == ["COLA0001", "COLB0001"]


def test_a_collection_archive_passes_verification(world: World, tmp_path: Path) -> None:
    path = tmp_path / "collection.zaf"
    world.service.backup_collection("COLA0001", str(path))

    assert VerifyService().verify_archive(str(path)).is_valid


@discrepancy("D7", "items filed only in a sub-collection are not part of the backup")
def test_a_collection_backup_includes_its_sub_collections_items(world: World) -> None:
    """`collection backup` documents that it traverses the entire collection hierarchy."""
    archive = backup_collection(world, "COLA0001")

    assert {"NOTE0001", "BOOK0001", "BK1PDF01"} <= set(archive.keys)


@discrepancy("D4", "a collection archive has no collections.json: names and tree are lost")
def test_a_collection_backup_records_the_collection_tree(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    assert archive.collections is not None
    assert {"COLA0001", "COLA1001", "COLA1A01"} <= {c["key"] for c in archive.collections}


@discrepancy("D8", "annotations are grandchildren of the items listed: they are not fetched")
def test_a_collection_backup_includes_pdf_annotations(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    assert {"ANN00001", "ANN00002"} <= set(archive.keys)


# =============================================================================================
# 4. A backup that is incomplete says so, and never destroys an earlier one
# =============================================================================================


def test_a_failing_listing_aborts_the_backup(world: World) -> None:
    world.lib.failing.add("items")

    out = BytesIO()
    with pytest.raises(Unavailable):
        world.service.backup_system(out)


def test_a_failing_collection_listing_aborts_the_backup(world: World) -> None:
    world.lib.failing.add("collections")

    out = BytesIO()
    with pytest.raises(Unavailable):
        world.service.backup_system(out)


def test_a_file_that_cannot_be_downloaded_is_listed_in_errors_log(world: World) -> None:
    world.lib.broken_files.add("PDF00001")

    archive = backup_system(world)

    assert "PDF00001" in archive.errors
    assert "PDF00001" not in archive.manifest["file_map"]
    assert "PDF00001" in archive.by_key, "the item itself must still be backed up"


def test_a_failed_backup_leaves_the_previous_backup_untouched(world: World, tmp_path: Path) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))
    previous = path.read_bytes()
    world.lib.failing.add("collections")

    target = str(path)
    with pytest.raises(Unavailable):
        world.service.backup_system(target)

    assert path.read_bytes() == previous


def test_a_failed_backup_leaves_no_partial_file_behind(world: World, tmp_path: Path) -> None:
    """First run (nothing to protect) or not, the directory only ever holds finished archives."""
    path = tmp_path / "library.zaf"
    world.lib.failing.add("collections")

    target = str(path)
    with pytest.raises(Unavailable):
        world.service.backup_system(target)

    assert os.listdir(tmp_path) == []


def test_an_interrupted_backup_cleans_up_and_keeps_the_previous_one(
    world: World, tmp_path: Path
) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))
    previous = path.read_bytes()

    def interrupt(_item: Any) -> None:
        raise KeyboardInterrupt

    target = str(path)
    with pytest.raises(KeyboardInterrupt):
        world.service.backup_system(target, on_item_processed=interrupt)

    assert path.read_bytes() == previous
    assert os.listdir(tmp_path) == ["library.zaf"]


def test_a_successful_backup_replaces_the_file_in_one_piece(world: World, tmp_path: Path) -> None:
    path = tmp_path / "library.zaf"
    path.write_bytes(b"an old, unrelated file")

    world.service.backup_system(str(path))

    assert Archive(path).keys
    assert os.listdir(tmp_path) == ["library.zaf"]


def test_a_new_backup_file_has_the_permissions_of_an_ordinary_file(
    world: World, tmp_path: Path
) -> None:
    """Whatever the umask gives a new file, not a private 0600."""
    if os.name == "nt":
        pytest.skip("POSIX permission bits")
    path = tmp_path / "library.zaf"
    umask = os.umask(0)
    os.umask(umask)

    world.service.backup_system(str(path))

    assert stat.S_IMODE(path.stat().st_mode) == 0o666 & ~umask


def test_a_backup_over_an_existing_file_keeps_its_permissions(world: World, tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX permission bits")
    path = tmp_path / "library.zaf"
    path.write_bytes(b"old")
    path.chmod(0o640)

    world.service.backup_system(str(path))

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


# =============================================================================================
# 5. What a full backup still lacks (decisions or gaps; see the report)
# =============================================================================================


@discrepancy("D1", "only imported_file/linked_file are downloaded; the file is silently dropped")
@pytest.mark.parametrize(
    ("key", "content"), [("SNP00001", SNAPSHOT), ("EMB00001", PNG)], ids=["snapshot", "note-image"]
)
def test_every_stored_file_is_saved_snapshots_and_note_images_too(
    world: World, key: str, content: bytes
) -> None:
    archive = backup_system(world)

    assert key in archive.manifest["file_map"], f"{key}: file not saved and not reported"
    assert archive.file_of(key) == content


@discrepancy("D2", "the /items listing excludes the trash and /items/trash is never read")
def test_items_in_the_trash_are_backed_up_with_their_deleted_flag(world: World) -> None:
    archive = backup_system(world)

    assert {"TRSH0001", "TRSHN001"} <= set(archive.keys)
    assert archive.by_key["TRSH0001"]["data"]["deleted"] == 1


@discrepancy("D3", "manifest.json has no library type/id: a restore cannot tell group from user")
def test_the_manifest_records_which_library_the_archive_came_from(world: World) -> None:
    manifest = backup_system(world).manifest

    library = manifest.get("library") or {}
    assert str(library.get("type")) == world.lib.library_type
    assert str(library.get("id")) == world.lib.library_id


@discrepancy("D9", "the /searches endpoint is never read")
def test_saved_searches_are_backed_up(world: World) -> None:
    archive = backup_system(world)

    assert "searches.json" in archive.names
    assert [s["key"] for s in json.loads(archive.zf.read("searches.json"))] == ["SRCH0001"]


@discrepancy("D6", "both files get the same path in the zip; the archive then fails its own verify")
def test_attachments_with_the_same_file_name_do_not_overwrite_each_other(
    world: World, tmp_path: Path
) -> None:
    """Zotero lets one item hold several attachments called `Full Text.pdf`."""
    for key, content in (("DUP00001", b"ONE"), ("DUP00002", b"TWO-TWO")):
        world.lib.add_item(
            key,
            "attachment",
            parent="JRN00001",
            linkMode="imported_file",
            filename="Full Text.pdf",
            file=content,
        )
    path = tmp_path / "library.zaf"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        world.service.backup_system(str(path))

    archive = Archive(path)
    assert archive.file_of("DUP00001") == b"ONE"
    assert archive.file_of("DUP00002") == b"TWO-TWO"
    assert VerifyService().verify_archive(str(path)).is_valid


# =============================================================================================
# 6. The command line: `system backup` and `collection backup` against user and group libraries
# =============================================================================================


@dataclass
class CliRun:
    code: int
    out: str
    err: str


@dataclass
class Cli:
    server: FakeZoteroServer
    run: Callable[..., CliRun]


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Cli:
    from zotero_cli.cli.main import main

    for name in [n for n in os.environ if n.startswith("ZOTERO_")]:
        monkeypatch.delenv(name)
    server = _server()
    original_init = ZoteroHttpClient.__init__

    def init(self: ZoteroHttpClient, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.session = server.session()  # type: ignore[assignment]

    monkeypatch.setattr(ZoteroHttpClient, "__init__", init)

    def run(*argv: str, default: tuple = GROUP) -> CliRun:
        config = tmp_path / "config.toml"
        config.write_text(
            f'[zotero]\napi_key = "key"\nuser_id = "{USER[1]}"\n'
            f'library_id = "{default[1]}"\nlibrary_type = "{default[0]}"\n'
        )
        monkeypatch.setattr(sys, "argv", ["zotero-cli", "--config", str(config), *argv])
        code = 0
        try:
            main()
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else 1
        captured = capsys.readouterr()
        return CliRun(code, captured.out, captured.err)

    return Cli(server, run)


def _keys_in(path: Path) -> List[str]:
    return sorted(Archive(path).keys)


def test_cli_backs_up_the_group_library_set_in_the_configuration(cli: Cli, tmp_path: Path) -> None:
    out = tmp_path / "group.zaf"

    result = cli.run("system", "backup", "--output", str(out))

    assert result.code == 0
    assert "Backup complete" in result.out
    assert _keys_in(out) == sorted(ALL_LIVE)
    assert Archive(out).by_key["JRN00001"]["library"]["type"] == "group"
    assert cli.server.libraries[USER].requests == []


def test_cli_user_flag_backs_up_the_personal_library_instead(cli: Cli, tmp_path: Path) -> None:
    out = tmp_path / "user.zaf"

    result = cli.run("--user", "system", "backup", "--output", str(out))

    assert result.code == 0
    assert Archive(out).by_key["JRN00001"]["library"]["type"] == "user"
    assert cli.server.libraries[GROUP].requests == []


def test_cli_collection_backup_by_name_in_a_group(cli: Cli, tmp_path: Path) -> None:
    """`collection backup` has to resolve the name inside the selected library only."""
    cli.server.libraries[GROUP].requests.clear()
    out = tmp_path / "reviews.zaf"

    result = cli.run("collection", "backup", "--collection", "COLA0001", "--output", str(out))

    assert result.code == 0
    assert "Backup complete" in result.out
    assert "JRN00001" in _keys_in(out)
    assert cli.server.libraries[USER].requests == []


def test_cli_exits_1_and_does_not_claim_success_when_the_listing_fails(
    cli: Cli, tmp_path: Path
) -> None:
    cli.server.libraries[GROUP].failing.add("collections")

    result = cli.run("system", "backup", "--output", str(tmp_path / "x.zaf"))

    assert result.code == 1
    assert "Backup failed" in result.err
    assert "Backup complete" not in result.out


@discrepancy("D10", "`system backup` accepts only --output; the group comes from the config file")
def test_cli_selects_a_group_library_with_a_parameter_on_the_call(cli: Cli, tmp_path: Path) -> None:
    """The provisional flag is `--group <id>`, the counterpart of `--user`; the requirement is that
    the group is named on the call, whatever the personal default configured."""
    out = tmp_path / "group.zaf"

    result = cli.run("system", "backup", "--group", GROUP[1], "--output", str(out), default=USER)

    assert result.code == 0, result.err
    assert Archive(out).by_key["JRN00001"]["library"]["type"] == "group"
    assert cli.server.libraries[USER].requests == []


@discrepancy("D5", "errors.log is written but the command prints 'Backup complete' and exits 0")
def test_cli_signals_a_backup_that_lacks_files(cli: Cli, tmp_path: Path) -> None:
    cli.server.libraries[GROUP].broken_files.add("PDF00001")

    result = cli.run("system", "backup", "--output", str(tmp_path / "partial.zaf"))

    assert result.code == PartialFailure.exit_code
    assert "Backup complete" not in result.out


def test_cli_group_backup_matches_the_service_backup(cli: Cli, tmp_path: Path) -> None:
    """The command adds nothing and drops nothing compared with the service."""
    out = tmp_path / "group.zaf"
    cli.run("system", "backup", "--output", str(out))
    lib = cli.server.libraries[GROUP]
    client = ZoteroAPIClient("key", lib.library_id, lib.library_type)
    client.http.session = cli.server.session()  # type: ignore[assignment]
    direct = BytesIO()
    GatewayFactory.get_backup_service(client).backup_system(direct)

    assert Archive(out).data == Archive(direct.getvalue()).data
    assert Archive(out).collections == Archive(direct.getvalue()).collections
