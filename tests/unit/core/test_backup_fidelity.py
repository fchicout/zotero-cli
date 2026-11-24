"""What a backup (.zaf) has to contain to restore a Zotero library without loss.

The tests run the real stack (CLI handlers, gateway factory, `ZoteroAPIClient`, `BackupService`,
`VerifyService`) against `tests/zotero_fake.py`, an in-memory Zotero Web API, for a user library
and for a group library. They describe the required behaviour:

- the whole library (or one collection) goes in: every collection with its hierarchy, every
  item, sub-item, note, annotation and attachment file, with the item relationships Zotero
  Desktop and the Web Library show (parent/child, collection membership, related items, tags);
- the archive says which library it came from and passes `system verify`;
- a backup that cannot be complete says so, and never destroys an earlier backup.

The suite began as a review of the backup against that behaviour: eleven findings were first
recorded here as strict `xfail` tests (ids D1..D11) and fixed one by one, each removing its marker
(tracking issue #652). They are listed so a regression can be traced:

D1  files of `imported_url` (web snapshots) and `embedded_image` attachments were not saved (#655)
D2  items in the trash were not saved; now the `--trash` option (#662)
D3  the manifest did not record which library (user/group, id) the archive came from (#659)
D4  a collection backup had no collections.json: names and hierarchy were lost (#660)
D5  a backup missing files reported "Backup complete" and exited 0 (#656)
D6  two attachments of one item with the same file name overwrote each other (#654)
D7  a collection backup skipped the items of its sub-collections (#657)
D8  a collection backup skipped the annotations of the PDFs it contains (#658)
D9  saved searches were not saved (#663)
D10 no per-call parameter selected a group library: `--group` (#661)
D11 a failed run overwrote an earlier good backup at the same path (#653)
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

from tests.zotero_fake import (
    ALL_LIVE,
    GROUP,
    LIVE_KEYS,
    PDF,
    PNG,
    SNAPSHOT,
    USER,
    FakeLibrary,
    FakeZoteroServer,
    populate,
)
from zotero_cli.core.exceptions import AuthError, PartialFailure, Unavailable
from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.services.verify_service import VerifyService
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.infra.http_client import ZoteroHttpClient
from zotero_cli.infra.zotero_api import ZoteroAPIClient


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


def backup_system(world: World, **options: Any) -> Archive:
    out = BytesIO()
    world.service.backup_system(out, **options)
    return Archive(out.getvalue())


def backup_collection(world: World, key: str, **options: Any) -> Archive:
    out = BytesIO()
    world.service.backup_collection(key, out, **options)
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


def test_a_collection_backup_includes_its_sub_collections_items(world: World) -> None:
    """`collection backup` documents that it traverses the entire collection hierarchy."""
    archive = backup_collection(world, "COLA0001")

    assert {"NOTE0001", "BOOK0001", "BK1PDF01"} <= set(archive.keys)
    assert archive.file_of("BK1PDF01") == PDF + b"book"


def test_an_item_filed_in_several_sub_collections_is_backed_up_once(world: World) -> None:
    world.lib.add_item(
        "TWICE001", "book", collections=["COLA1001", "COLA1A01", "COLA0001"], title="Twice"
    )

    archive = backup_collection(world, "COLA0001")

    assert archive.keys.count("TWICE001") == 1
    assert len(archive.keys) == len(set(archive.keys))


def test_a_leaf_collection_backup_holds_only_its_own_items(world: World) -> None:
    archive = backup_collection(world, "COLA1A01")

    assert "BOOK0001" in archive.keys
    assert "NOTE0001" not in archive.keys
    assert "JRN00001" not in archive.keys


def test_a_middle_collection_backup_stops_at_its_own_sub_tree(world: World) -> None:
    archive = backup_collection(world, "COLA1001")

    assert {"NOTE0001", "BOOK0001"} <= set(archive.keys)
    assert "JRN00001" not in archive.keys, "an item of the parent collection is not included"


def test_the_manifest_lists_the_collections_a_backup_covers(world: World) -> None:
    manifest = backup_collection(world, "COLA0001").manifest

    assert manifest["collection_keys"] == ["COLA0001", "COLA1001", "COLA1A01"]
    assert manifest["root_collection_key"] == "COLA0001"


def test_a_parent_loop_in_the_data_cannot_hang_the_backup(world: World) -> None:
    """Zotero never produces one; a damaged database or a bad API answer might."""
    world.lib.collections["COLA0001"]["data"]["parentCollection"] = "COLA1A01"

    archive = backup_collection(world, "COLA0001")

    assert sorted(archive.manifest["collection_keys"]) == ["COLA0001", "COLA1001", "COLA1A01"]
    assert "BOOK0001" in archive.keys


def test_a_collection_backup_lists_each_collection_once(world: World) -> None:
    """One items listing per collection in the tree, not one per item."""
    world.lib.requests.clear()

    backup_collection(world, "COLA0001")

    assert world.lib.requests.count("collections") == 1
    listings = [r for r in world.lib.requests if r.endswith("/items/top")]
    assert sorted(listings) == [
        "collections/COLA0001/items/top",
        "collections/COLA1001/items/top",
        "collections/COLA1A01/items/top",
    ]


def test_a_collection_backup_records_the_collection_tree(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    assert archive.collections is not None
    by_key = {c["key"]: c for c in archive.collections}
    assert sorted(by_key) == ["COLA0001", "COLA1001", "COLA1A01"]
    assert by_key["COLA0001"]["data"]["name"] == "Reviews"
    assert by_key["COLA1001"]["data"]["parentCollection"] == "COLA0001"
    assert by_key["COLA1A01"]["data"]["parentCollection"] == "COLA1001"
    assert by_key["COLA1A01"]["data"]["name"] == "Drafts"


def test_a_leaf_collection_archive_has_just_its_own_record(world: World) -> None:
    archive = backup_collection(world, "COLA1A01")

    assert archive.collections is not None
    assert [c["key"] for c in archive.collections] == ["COLA1A01"]


def test_a_middle_collection_keeps_its_record_as_the_api_gave_it(world: World) -> None:
    """Its parent is not in the archive; the reference stays, a restore treats it as top level."""
    archive = backup_collection(world, "COLA1001")

    assert archive.collections is not None
    by_key = {c["key"]: c for c in archive.collections}
    assert sorted(by_key) == ["COLA1001", "COLA1A01"]
    assert by_key["COLA1001"]["data"]["parentCollection"] == "COLA0001"


def test_collections_outside_the_backup_are_not_added(world: World) -> None:
    """An article filed in `Reviews` and in an unrelated `Reading list`: only the first is kept."""
    archive = backup_collection(world, "COLA0001")

    assert archive.collections is not None
    assert "COLB0001" not in {c["key"] for c in archive.collections}
    assert archive.by_key["JRN00001"]["data"]["collections"] == ["COLA0001", "COLB0001"]


def test_a_collection_archive_counts_and_verifies_its_collections(
    world: World, tmp_path: Path
) -> None:
    path = tmp_path / "collection.zaf"
    world.service.backup_collection("COLA0001", str(path))

    report = VerifyService().verify_archive(str(path))

    assert report.is_valid, report.errors
    assert report.collection_count == 3
    assert (report.manifest or {})["counts"]["collections"] == 3


def _drop_member(source: Path, target: Path, name: str) -> None:
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w") as dst:
        for info in src.infolist():
            if info.filename != name:
                dst.writestr(info.filename, src.read(info.filename))


def test_verification_catches_a_collection_archive_without_its_root(
    world: World, tmp_path: Path
) -> None:
    path = tmp_path / "collection.zaf"
    world.service.backup_collection("COLA1001", str(path))
    changed = tmp_path / "changed.zaf"

    def other_root(manifest: Dict[str, Any]) -> None:
        manifest["root_collection_key"] = "COLA0001"

    _rewrite_manifest(path, changed, other_root)

    report = VerifyService().verify_archive(str(changed))

    assert not report.is_valid
    assert any("root collection COLA0001" in e for e in report.errors)


def test_a_collection_archive_from_before_1_2_still_verifies(world: World, tmp_path: Path) -> None:
    """Older collection backups have no collections.json."""
    path = tmp_path / "collection.zaf"
    world.service.backup_collection("COLA0001", str(path))
    old = tmp_path / "old.zaf"
    _drop_member(path, old, "collections.json")

    report = VerifyService().verify_archive(str(old))

    assert report.is_valid, report.errors


def test_restoring_a_collection_archive_rebuilds_its_sub_tree(world: World, tmp_path: Path) -> None:
    """A restore into an empty library creates the collections with their names and nesting
    and files each item in the right one; collections the archive does not hold are dropped."""
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway
    from zotero_cli.core.services.restore_service import RestoreService

    path = tmp_path / "collection.zaf"
    world.service.backup_collection("COLA0001", str(path))
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_items.return_value = iter([])
    gateway.get_all_collections.return_value = []
    created: List[Any] = []

    def create_collection(name: str, parent_key: Optional[str] = None) -> str:
        created.append((name, parent_key))
        return f"NEW{len(created)}"

    new_items: Dict[str, Dict[str, Any]] = {}

    def create_item(data: Dict[str, Any]) -> str:
        # annotations have no restore path yet (#652) and arrive here without a title
        new_items[data.get("title", data["itemType"])] = data
        return f"ITM{len(new_items)}"

    gateway.create_collection.side_effect = create_collection
    gateway.create_generic_item.side_effect = create_item

    report = RestoreService(gateway, gateway, gateway, gateway).restore_archive(str(path))

    assert report.errors == []
    assert created == [("Reviews", None), ("2025", "NEW1"), ("Drafts", "NEW2")]
    assert new_items["A study of backups"]["collections"] == ["NEW1"]
    assert new_items["The book"]["collections"] == ["NEW3"]


def test_a_collection_backup_includes_pdf_annotations(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    assert {"ANN00001", "ANN00002"} <= set(archive.keys)
    assert archive.by_key["ANN00001"]["data"]["parentItem"] == "PDF00001"


def test_annotations_come_after_their_pdf_in_the_archive(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    keys = archive.keys
    assert keys.index("JRN00001") < keys.index("PDF00001") < keys.index("ANN00001")


def test_a_collection_backup_includes_the_images_embedded_in_its_notes(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    assert archive.by_key["EMB00001"]["data"]["parentItem"] == "NOT00001"
    assert archive.file_of("EMB00001") == PNG


def test_the_annotations_of_a_stand_alone_pdf_are_included_too(world: World) -> None:
    world.lib.add_item("ANN0STND", "annotation", parent="STND0001", annotationType="highlight")

    archive = backup_collection(world, "COLA0001")

    assert "ANN0STND" in archive.keys


def test_a_pdf_without_annotations_adds_nothing(world: World) -> None:
    archive = backup_collection(world, "COLA1A01")

    assert sorted(archive.keys) == ["BK1PDF01", "BOOK0001"]


def test_collection_and_library_backups_hold_the_same_annotations(world: World) -> None:
    from_collection = {k for k in backup_collection(world, "COLA0001").keys if k.startswith("ANN")}
    from_library = {k for k in backup_system(world).keys if k.startswith("ANN")}

    assert from_collection == from_library == {"ANN00001", "ANN00002"}


def test_annotations_cost_requests_per_listing_not_per_pdf(world: World) -> None:
    """Ten more articles with a PDF and an annotation each: the annotations are found with a
    scan of the annotation type, not one children request per PDF."""
    pdfs = []
    for i in range(10):
        world.lib.add_item(f"ART{i:05d}", "book", collections=["COLA0001"], title=f"b{i}")
        world.lib.add_item(
            f"PDF{i:05d}",
            "attachment",
            parent=f"ART{i:05d}",
            linkMode="imported_file",
            filename=f"p{i}.pdf",
            file=b"%PDF" + bytes([i]),
        )
        world.lib.add_item(f"ANN{i:05d}", "annotation", parent=f"PDF{i:05d}")
        pdfs.append(f"PDF{i:05d}")
    world.lib.requests.clear()

    archive = backup_collection(world, "COLA0001")

    assert {f"ANN{i:05d}" for i in range(10)} <= set(archive.keys)
    per_pdf = [r for r in world.lib.requests if r in {f"items/{k}/children" for k in pdfs}]
    assert per_pdf == []


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


@pytest.mark.parametrize(
    ("key", "content"), [("SNP00001", SNAPSHOT), ("EMB00001", PNG)], ids=["snapshot", "note-image"]
)
def test_every_stored_file_is_saved_snapshots_and_note_images_too(
    world: World, key: str, content: bytes
) -> None:
    archive = backup_system(world)

    assert key in archive.manifest["file_map"], f"{key}: file not saved and not reported"
    assert archive.file_of(key) == content


def test_a_stored_file_that_cannot_be_downloaded_is_reported_not_skipped(world: World) -> None:
    world.lib.broken_files.update({"SNP00001", "EMB00001"})

    archive = backup_system(world)

    assert "SNP00001" in archive.errors
    assert "EMB00001" in archive.errors
    assert "SNP00001" not in archive.manifest["file_map"]


@pytest.mark.parametrize(
    ("fields", "expected_name"),
    [
        ({"contentType": "application/pdf"}, "NONAME01.pdf"),
        ({"contentType": "text/html"}, "NONAME01.html"),
        ({}, "NONAME01"),
        ({"title": "../.."}, "NONAME01"),
    ],
    ids=["pdf", "html", "no-content-type", "title-of-dots"],
)
def test_a_stored_file_without_a_name_is_still_saved(
    world: World, fields: Dict[str, Any], expected_name: str
) -> None:
    """Such an attachment used to be skipped without a trace."""
    world.lib.add_item(
        "NONAME01",
        "attachment",
        parent="JRN00001",
        linkMode="imported_url",
        file=b"nameless",
        **fields,
    )

    archive = backup_system(world)

    assert archive.file_of("NONAME01") == b"nameless"
    assert archive.manifest["file_map"]["NONAME01"]["path"].endswith("/" + expected_name)


def test_a_web_link_is_not_downloaded_and_not_an_error(world: World) -> None:
    archive = backup_system(world)

    assert "LNK00001" not in archive.manifest["file_map"]
    assert "LNK00001" not in archive.errors
    assert "items/LNK00001/file" not in world.lib.requests


def test_the_trash_is_left_out_by_default(world: World) -> None:
    library = backup_system(world)
    collection = backup_collection(world, "COLA0001")

    for archive in (library, collection):
        assert "TRSH0001" not in archive.keys
        assert "TRSHN001" not in archive.keys
        assert archive.manifest["includes_trash"] is False


def test_the_trash_option_adds_trashed_items_with_their_children_and_flag(world: World) -> None:
    archive = backup_system(world, include_trash=True)

    assert {"TRSH0001", "TRSHN001"} <= set(archive.keys)
    assert archive.by_key["TRSH0001"]["data"]["deleted"] == 1
    assert archive.by_key["TRSHN001"]["data"]["parentItem"] == "TRSH0001"
    assert archive.manifest["includes_trash"] is True
    assert archive.manifest["counts"]["items"] == len(ALL_LIVE) + 2
    assert set(ALL_LIVE) <= set(archive.keys), "everything else is still there"


def test_the_children_of_a_trashed_parent_are_found_even_if_the_trash_does_not_list_them(
    world: World,
) -> None:
    world.lib.trash_lists_children = False

    archive = backup_system(world, include_trash=True)

    assert {"TRSH0001", "TRSHN001"} <= set(archive.keys)


def _trash_an_annotated_pdf(world: World) -> None:
    world.lib.add_item(
        "TRSHPDF1",
        "attachment",
        parent="TRSH0001",
        linkMode="imported_file",
        filename="deleted.pdf",
        contentType="application/pdf",
        file=PDF + b"deleted",
    )
    world.lib.add_item("TRSHANN1", "annotation", parent="TRSHPDF1", annotationType="highlight")


@pytest.mark.parametrize("scope", ["library", "collection"])
def test_a_trashed_item_keeps_its_pdf_and_annotations(world: World, scope: str) -> None:
    _trash_an_annotated_pdf(world)
    world.lib.trash_lists_children = False

    archive = (
        backup_system(world, include_trash=True)
        if scope == "library"
        else backup_collection(world, "COLA0001", include_trash=True)
    )

    assert archive.file_of("TRSHPDF1") == PDF + b"deleted"
    assert "TRSHANN1" in archive.keys


def test_a_collection_backup_takes_only_the_trash_filed_in_the_collection_tree(
    world: World,
) -> None:
    world.lib.add_item(
        "TRSHSUB1", "book", collections=["COLA1A01"], title="Deleted, deep", deleted=True
    )
    world.lib.add_item(
        "TRSHOTH1", "book", collections=["COLB0001"], title="Deleted, elsewhere", deleted=True
    )
    world.lib.add_item("TRSHFREE", "book", title="Deleted, unfiled", deleted=True)

    archive = backup_collection(world, "COLA0001", include_trash=True)

    assert {"TRSH0001", "TRSHN001", "TRSHSUB1"} <= set(archive.keys)
    assert "TRSHOTH1" not in archive.keys
    assert "TRSHFREE" not in archive.keys
    assert archive.manifest["includes_trash"] is True


def test_a_note_trashed_on_its_own_comes_with_the_backup_of_its_live_parent(world: World) -> None:
    world.lib.add_item("TRSHNOTE", "note", parent="JRN00001", note="gone", deleted=True)

    library = backup_system(world, include_trash=True)
    collection = backup_collection(world, "COLA0001", include_trash=True)
    plain = backup_system(world)

    assert "TRSHNOTE" in library.keys
    assert "TRSHNOTE" in collection.keys
    assert "TRSHNOTE" not in plain.keys


def test_an_archive_with_the_trash_verifies(world: World, tmp_path: Path) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path), include_trash=True)

    report = VerifyService().verify_archive(str(path))

    assert report.is_valid, report.errors
    assert (report.manifest or {})["includes_trash"] is True


def test_restoring_a_trashed_item_sends_its_deleted_flag(world: World, tmp_path: Path) -> None:
    """The archive keeps `deleted`, and the restore passes it on when it creates the item."""
    from unittest.mock import create_autospec

    from zotero_cli.core.interfaces import ZoteroGateway
    from zotero_cli.core.services.restore_service import RestoreService

    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path), include_trash=True)
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_items.return_value = iter([])
    gateway.get_all_collections.return_value = []
    gateway.create_collection.return_value = "NEWCOL"
    created: Dict[str, Dict[str, Any]] = {}

    def create_item(data: Dict[str, Any]) -> str:
        created[data.get("title", data["itemType"])] = data
        return f"ITM{len(created)}"

    gateway.create_generic_item.side_effect = create_item

    RestoreService(gateway, gateway, gateway, gateway).restore_archive(str(path))

    assert created["Deleted book"]["deleted"] == 1
    assert "deleted" not in created["The book"]


def test_the_manifest_records_which_library_the_archive_came_from(world: World) -> None:
    manifest = backup_system(world).manifest

    assert manifest["library"] == {
        "type": world.lib.library_type,
        "id": world.lib.library_id,
        "name": world.lib.name,
    }


def test_a_collection_archive_records_its_library_too(world: World) -> None:
    manifest = backup_collection(world, "COLA0001").manifest

    assert manifest["library"]["type"] == world.lib.library_type
    assert manifest["library"]["id"] == world.lib.library_id


def test_the_manifest_is_format_1_2_and_counts_what_it_holds(world: World) -> None:
    archive = backup_system(world)

    assert archive.manifest["version"] == "1.2"
    assert archive.manifest["counts"] == {
        "items": len(archive.data),
        "collections": len(archive.collections or []),
        "files": len(archive.manifest["file_map"]),
        "searches": 1,
    }
    assert archive.manifest["includes_trash"] is False


def test_an_empty_library_still_says_where_it_is_from(tmp_path: Path) -> None:
    """No item or collection to take the library from: the gateway that was asked says it."""
    server = FakeZoteroServer()
    lib = server.register(FakeLibrary(*GROUP))
    client = ZoteroAPIClient("key", lib.library_id, lib.library_type)
    client.http.session = server.session()  # type: ignore[assignment]
    path = tmp_path / "empty.zaf"

    GatewayFactory.get_backup_service(client).backup_system(str(path))

    manifest = Archive(path).manifest
    assert manifest["library"] == {"type": "group", "id": "777"}
    assert manifest["counts"] == {"items": 0, "collections": 0, "files": 0, "searches": 0}


def test_without_a_known_library_the_stub_on_the_items_is_used(world: World) -> None:
    service = BackupService(
        world.service.items, world.service.collections, world.service.attachments
    )
    out = BytesIO()

    service.backup_system(out)

    assert Archive(out.getvalue()).manifest["library"]["id"] == world.lib.library_id


def test_verification_shows_the_library_and_accepts_the_counts(
    world: World, tmp_path: Path
) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))

    report = VerifyService().verify_archive(str(path))

    assert report.is_valid, report.errors
    assert (report.manifest or {})["library"]["id"] == world.lib.library_id


def _rewrite_manifest(source: Path, target: Path, change: Callable[[Dict[str, Any]], None]) -> None:
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w") as dst:
        for info in src.infolist():
            content = src.read(info.filename)
            if info.filename == "manifest.json":
                manifest = json.loads(content)
                change(manifest)
                content = json.dumps(manifest).encode()
            dst.writestr(info.filename, content)


@pytest.mark.parametrize("field", ["items", "files", "collections"])
def test_verification_catches_an_archive_that_holds_other_counts_than_it_says(
    world: World, tmp_path: Path, field: str
) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))
    changed = tmp_path / "changed.zaf"

    def lie(manifest: Dict[str, Any]) -> None:
        manifest["counts"][field] += 1

    _rewrite_manifest(path, changed, lie)

    report = VerifyService().verify_archive(str(changed))

    assert not report.is_valid
    messages = [e for e in report.errors if "manifest counts" in e]
    assert [m for m in messages if field in m]


def test_saved_searches_are_backed_up(world: World) -> None:
    archive = backup_system(world)

    searches = json.loads(archive.zf.read("searches.json"))
    assert [s["key"] for s in searches] == ["SRCH0001"]
    assert searches[0]["data"]["name"] == "Unread"
    assert searches[0]["data"]["conditions"] == [{"condition": "tag"}]


def test_a_library_without_saved_searches_still_writes_the_file(world: World) -> None:
    world.lib.searches.clear()

    archive = backup_system(world)

    assert json.loads(archive.zf.read("searches.json")) == []
    assert archive.manifest["counts"]["searches"] == 0


def test_a_collection_backup_has_no_saved_searches(world: World) -> None:
    archive = backup_collection(world, "COLA0001")

    assert "searches.json" not in archive.names
    assert "searches" not in archive.manifest["counts"]


def test_more_than_one_page_of_saved_searches_is_complete(world: World) -> None:
    for i in range(130):
        world.lib.searches[f"SRCHX{i:03d}"] = {
            "key": f"SRCHX{i:03d}",
            "version": i,
            "data": {"key": f"SRCHX{i:03d}", "name": f"s{i}", "conditions": []},
        }

    archive = backup_system(world)

    assert len(json.loads(archive.zf.read("searches.json"))) == 131
    assert archive.manifest["counts"]["searches"] == 131


def test_verification_counts_the_saved_searches(world: World, tmp_path: Path) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))

    report = VerifyService().verify_archive(str(path))

    assert report.is_valid, report.errors
    assert report.search_count == 1


def test_verification_catches_a_searches_file_that_is_not_json(
    world: World, tmp_path: Path
) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))
    broken = tmp_path / "broken.zaf"
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(broken, "w") as dst:
        for info in src.infolist():
            content = b"{not json" if info.filename == "searches.json" else src.read(info.filename)
            dst.writestr(info.filename, content)

    report = VerifyService().verify_archive(str(broken))

    assert not report.is_valid
    assert any("searches.json" in e for e in report.errors)


def test_an_archive_from_before_saved_searches_still_verifies(world: World, tmp_path: Path) -> None:
    path = tmp_path / "library.zaf"
    world.service.backup_system(str(path))
    old = tmp_path / "old.zaf"
    _drop_member(path, old, "searches.json")

    def forget(manifest: Dict[str, Any]) -> None:
        manifest["counts"].pop("searches")

    older = tmp_path / "older.zaf"
    _rewrite_manifest(old, older, forget)

    report = VerifyService().verify_archive(str(older))

    assert report.is_valid, report.errors


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
        warnings.simplefilter("error")  # zipfile warns "Duplicate name" on a collision
        world.service.backup_system(str(path))

    archive = Archive(path)
    assert archive.file_of("DUP00001") == b"ONE"
    assert archive.file_of("DUP00002") == b"TWO-TWO"
    assert VerifyService().verify_archive(str(path)).is_valid


def _add_files(world: World, parent: Optional[str], names: List[str]) -> Dict[str, bytes]:
    """Attachments called `names` (one stored file each), returned as key -> content."""
    content: Dict[str, bytes] = {}
    for index, name in enumerate(names):
        key = f"FIL{index:05d}"
        content[key] = f"content {index}".encode()
        world.lib.add_item(
            key,
            "attachment",
            parent=parent,
            collections=None if parent else ["COLA0001"],
            linkMode="imported_file",
            filename=name,
            file=content[key],
        )
    return content


@pytest.mark.parametrize(
    ("parent", "names"),
    [
        ("JRN00001", ["same.pdf", "same.pdf", "same.pdf"]),
        ("JRN00001", ["Paper.pdf", "paper.PDF"]),
        (None, ["loose.pdf", "loose.pdf"]),
    ],
    ids=["three-with-one-name", "names-differing-only-in-case", "stand-alone-files"],
)
def test_every_attachment_keeps_its_own_file(
    world: World, tmp_path: Path, parent: Optional[str], names: List[str]
) -> None:
    expected = _add_files(world, parent, names)
    path = tmp_path / "library.zaf"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        world.service.backup_system(str(path))

    archive = Archive(path)
    paths = [archive.manifest["file_map"][key]["path"] for key in expected]
    assert len({p.casefold() for p in paths}) == len(paths)
    for key, content in expected.items():
        assert archive.file_of(key) == content
    assert VerifyService().verify_archive(str(path)).is_valid


def test_a_collection_backup_also_keeps_same_named_attachments_apart(world: World) -> None:
    expected = _add_files(world, "JRN00001", ["same.pdf", "same.pdf"])

    archive = backup_collection(world, "COLA0001")

    for key, content in expected.items():
        assert archive.file_of(key) == content


def test_file_names_that_do_not_collide_keep_their_path(world: World) -> None:
    """Existing archives and users see the same layout as before."""
    _add_files(world, "JRN00001", ["same.pdf", "same.pdf"])

    file_map = backup_system(world).manifest["file_map"]

    assert file_map["PDF00001"]["path"] == "attachments/JRN00001/study.pdf"
    assert file_map["BK1PDF01"]["path"] == "attachments/BOOK0001/book.pdf"
    assert file_map["STND0001"]["path"] == "attachments/orphan/loose.pdf"
    assert file_map["FIL00000"]["path"] == "attachments/JRN00001/same.pdf"
    assert file_map["FIL00001"]["path"] == "attachments/JRN00001/same-FIL00001.pdf"


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


def test_cli_exits_5_and_does_not_claim_success_when_the_listing_fails(
    cli: Cli, tmp_path: Path
) -> None:
    cli.server.libraries[GROUP].failing.add("collections")

    result = cli.run("system", "backup", "--output", str(tmp_path / "x.zaf"))

    assert result.code == Unavailable.exit_code
    assert "unavailable" in result.err
    assert "Backup complete" not in result.out


def test_cli_selects_a_group_library_with_a_parameter_on_the_call(cli: Cli, tmp_path: Path) -> None:
    """`--group <id>`, the counterpart of `--user`: the group is named on the call, whatever
    personal library the configuration names by default."""
    out = tmp_path / "group.zaf"

    result = cli.run("--group", GROUP[1], "system", "backup", "--output", str(out), default=USER)

    assert result.code == 0, result.err
    assert Archive(out).by_key["JRN00001"]["library"]["type"] == "group"
    assert Archive(out).manifest["library"]["id"] == GROUP[1]
    assert cli.server.libraries[USER].requests == []


def test_a_group_url_is_accepted_too(cli: Cli, tmp_path: Path) -> None:
    out = tmp_path / "group.zaf"
    url = f"https://www.zotero.org/groups/{GROUP[1]}/lab-group"

    result = cli.run("--group", url, "system", "backup", "--output", str(out), default=USER)

    assert result.code == 0, result.err
    assert Archive(out).manifest["library"]["id"] == GROUP[1]


def test_a_collection_backup_can_name_the_group_on_the_call(cli: Cli, tmp_path: Path) -> None:
    out = tmp_path / "reviews.zaf"

    result = cli.run(
        "--group",
        GROUP[1],
        "collection",
        "backup",
        "--collection",
        "COLA0001",
        "--output",
        str(out),
        default=USER,
    )

    assert result.code == 0, result.err
    assert "JRN00001" in _keys_in(out)
    assert cli.server.libraries[USER].requests == []


def test_the_backup_says_which_library_it_is_reading(cli: Cli, tmp_path: Path) -> None:
    result = cli.run(
        "--group", GROUP[1], "system", "backup", "--output", str(tmp_path / "g.zaf"), default=USER
    )

    assert "(group library 777)" in " ".join(result.out.split()), "Rich wraps long lines"


def test_the_next_run_without_the_flag_goes_back_to_the_configured_library(
    cli: Cli, tmp_path: Path
) -> None:
    cli.run(
        "--group", GROUP[1], "system", "backup", "--output", str(tmp_path / "a.zaf"), default=USER
    )
    second = tmp_path / "b.zaf"

    cli.run("system", "backup", "--output", str(second), default=USER)

    assert Archive(second).manifest["library"]["type"] == "user"


def test_system_info_shows_the_chosen_group(cli: Cli) -> None:
    result = cli.run("--group", GROUP[1], "system", "info", default=USER)

    assert "Library ID:  777" in result.out
    assert "Library Type: group" in result.out


def test_user_and_group_cannot_be_combined(cli: Cli, tmp_path: Path) -> None:
    result = cli.run(
        "--user", "--group", GROUP[1], "system", "backup", "--output", str(tmp_path / "x.zaf")
    )

    assert result.code == 2
    assert "not allowed with" in result.err


@pytest.mark.parametrize("value", ["abc", "0", "-3", "https://www.zotero.org/users/42"])
def test_a_group_that_is_not_one_is_a_usage_error(cli: Cli, tmp_path: Path, value: str) -> None:
    result = cli.run("--group", value, "system", "backup", "--output", str(tmp_path / "x.zaf"))

    assert result.code == 2
    assert "not a group" in result.err


def test_a_group_the_key_cannot_read_is_an_authentication_error(cli: Cli, tmp_path: Path) -> None:
    secret = FakeLibrary("group", "999", name="Private")
    secret.forbidden = True
    cli.server.register(secret)

    result = cli.run("--group", "999", "system", "backup", "--output", str(tmp_path / "x.zaf"))

    assert result.code == AuthError.exit_code
    assert "Traceback" not in result.err


def test_cli_signals_a_backup_that_lacks_files(cli: Cli, tmp_path: Path) -> None:
    cli.server.libraries[GROUP].broken_files.add("PDF00001")
    out = tmp_path / "partial.zaf"

    result = cli.run("system", "backup", "--output", str(out))

    assert result.code == PartialFailure.exit_code
    assert "Backup complete" not in result.out
    assert "incomplete" in result.err
    assert "errors.log" in result.err
    assert "PDF00001" in result.err
    assert "PDF00001" in Archive(out).by_key, "the archive is still written"


def test_cli_collection_backup_also_signals_missing_files(cli: Cli, tmp_path: Path) -> None:
    cli.server.libraries[GROUP].broken_files.add("PDF00001")

    result = cli.run(
        "collection", "backup", "--collection", "COLA0001", "--output", str(tmp_path / "c.zaf")
    )

    assert result.code == PartialFailure.exit_code
    assert "Backup complete" not in result.out


def test_cli_linked_files_are_a_note_not_a_failure(cli: Cli, tmp_path: Path) -> None:
    """A linked file lives on the user's computer: the Web API cannot back it up."""
    out = tmp_path / "linked.zaf"

    result = cli.run("system", "backup", "--output", str(out))

    assert result.code == 0
    assert "Backup complete" in result.out
    assert "1 linked file(s)" in result.out
    assert "SKIPPED" in Archive(out).errors


def test_the_service_reports_what_it_wrote_and_what_it_could_not(world: World) -> None:
    world.lib.broken_files.add("BK1PDF01")

    report = world.service.backup_system(BytesIO())

    assert report.items == len(ALL_LIVE)
    assert report.files == 5  # all stored files except the broken book PDF
    assert not report.complete
    assert [e for e in report.errors if "BK1PDF01" in e]
    assert [s for s in report.skipped if "LFL00001" in s]


def test_a_complete_backup_has_no_errors_even_with_linked_files(world: World) -> None:
    report = world.service.backup_system(BytesIO())

    assert report.complete
    assert report.errors == []
    assert len(report.skipped) == 1


def test_verify_tells_how_many_problems_the_archive_logged(cli: Cli, tmp_path: Path) -> None:
    cli.server.libraries[GROUP].broken_files.add("PDF00001")
    out = tmp_path / "partial.zaf"
    cli.run("system", "backup", "--output", str(out))

    result = cli.run("system", "verify", "--file", str(out))

    assert result.code == 0, "the archive itself is intact"
    assert "ARCHIVE IS VALID" in result.out
    assert "errors.log lists 1 problem(s)" in result.out
    assert "1 linked file(s) were not backed up" in result.out


def test_verify_stays_quiet_about_a_clean_archive(cli: Cli, tmp_path: Path) -> None:
    out = tmp_path / "clean.zaf"
    cli.server.libraries[GROUP].items.pop("LFL00001")
    cli.run("system", "backup", "--output", str(out))

    result = cli.run("system", "verify", "--file", str(out))

    assert "ARCHIVE IS VALID" in result.out
    assert "errors.log" not in result.out


def _group_archive(cli: Cli, tmp_path: Path) -> Path:
    path = tmp_path / "group.zaf"
    assert cli.run("system", "backup", "--output", str(path)).code == 0
    return path


def test_restore_into_the_library_the_archive_came_from_does_not_warn(
    cli: Cli, tmp_path: Path
) -> None:
    path = _group_archive(cli, tmp_path)

    result = cli.run("system", "restore", "--file", str(path))

    assert result.code == 0
    assert "different" not in result.out
    assert "Warning" not in result.out


def test_a_restore_preview_into_another_library_warns(cli: Cli, tmp_path: Path) -> None:
    path = _group_archive(cli, tmp_path)

    result = cli.run("--user", "system", "restore", "--file", str(path))

    assert result.code == 0, "a preview writes nothing: it only warns"
    assert "group library 777" in result.out
    assert "user library 42" in result.out


def test_applying_a_restore_into_another_library_needs_confirmation(
    cli: Cli, tmp_path: Path
) -> None:
    """No terminal here to ask on, so it refuses (usage error) instead of guessing."""
    path = _group_archive(cli, tmp_path)

    result = cli.run("--user", "system", "restore", "--file", str(path), "--execute")

    assert result.code == 2
    assert "--yes" in result.err


def test_yes_confirms_a_restore_into_another_library(cli: Cli, tmp_path: Path) -> None:
    path = _group_archive(cli, tmp_path)

    result = cli.run("--user", "system", "restore", "--file", str(path), "--execute", "--yes")

    assert "no terminal" not in result.err
    assert "restore cancelled" not in result.err
    assert "user library 42" in result.out


def test_an_archive_without_a_library_restores_without_a_warning(cli: Cli, tmp_path: Path) -> None:
    """Archives from before format 1.2 do not say where they came from."""
    path = _group_archive(cli, tmp_path)
    old = tmp_path / "old.zaf"
    _rewrite_manifest(path, old, lambda m: m.pop("library"))

    result = cli.run("--user", "system", "restore", "--file", str(old), "--execute")

    assert "Warning" not in result.out
    assert result.code != 2


def test_cli_trash_option_on_both_backup_commands(cli: Cli, tmp_path: Path) -> None:
    system_out = tmp_path / "all.zaf"
    collection_out = tmp_path / "col.zaf"

    plain = cli.run("system", "backup", "--output", str(tmp_path / "plain.zaf"))
    system = cli.run("system", "backup", "--trash", "--output", str(system_out))
    collection = cli.run(
        "collection",
        "backup",
        "--collection",
        "COLA0001",
        "--trash",
        "--output",
        str(collection_out),
    )

    assert plain.code == system.code == collection.code == 0
    assert "TRSH0001" not in _keys_in(tmp_path / "plain.zaf")
    assert "TRSH0001" in _keys_in(system_out)
    assert "TRSH0001" in _keys_in(collection_out)


def test_verify_says_when_an_archive_includes_the_trash(cli: Cli, tmp_path: Path) -> None:
    out = tmp_path / "all.zaf"
    cli.run("system", "backup", "--trash", "--output", str(out))

    result = cli.run("system", "verify", "--file", str(out))

    assert "Includes the items that were in the Zotero trash" in result.out


def test_verify_shows_the_number_of_saved_searches(cli: Cli, tmp_path: Path) -> None:
    out = tmp_path / "all.zaf"
    cli.run("system", "backup", "--output", str(out))

    result = cli.run("system", "verify", "--file", str(out))

    assert "Saved searches: 1" in result.out


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
