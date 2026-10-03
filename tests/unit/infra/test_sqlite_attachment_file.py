import sqlite3

import pytest

from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway


@pytest.fixture
def library(tmp_path):
    (tmp_path / "library").mkdir()
    tmp_path = tmp_path / "library"
    database = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(database)
    conn.executescript(
        """
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER,
            libraryID INTEGER, itemTypeID INTEGER, dateAdded TEXT, dateModified TEXT,
            clientDateModified TEXT, synced INTEGER DEFAULT 1);
        CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INTEGER,
            linkMode INTEGER, contentType TEXT, path TEXT);
        """
    )
    conn.commit()
    conn.close()
    return tmp_path


def add(library, key, path, link_mode=0):
    conn = sqlite3.connect(library / "zotero.sqlite")
    item_id = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] + 1
    conn.execute("INSERT INTO items (itemID, key, libraryID) VALUES (?, ?, 1)", (item_id, key))
    conn.execute(
        "INSERT INTO itemAttachments VALUES (?, NULL, ?, 'application/pdf', ?)",
        (item_id, link_mode, path),
    )
    conn.commit()
    conn.close()


def download(library, key):
    target = library / "out.pdf"
    ok = SqliteZoteroGateway(str(library / "zotero.sqlite")).download_attachment(key, str(target))
    return ok, target


def test_copies_a_stored_file_from_the_storage_folder(library):
    (library / "storage" / "PDFKEY01").mkdir(parents=True)
    (library / "storage" / "PDFKEY01" / "paper.pdf").write_bytes(b"%PDF-bytes")
    add(library, "PDFKEY01", "storage:paper.pdf")

    ok, target = download(library, "PDFKEY01")

    assert ok
    assert target.read_bytes() == b"%PDF-bytes"


def test_copies_a_linked_file_by_its_absolute_path(library):
    elsewhere = library.parent / "linked.pdf"
    elsewhere.write_bytes(b"linked")
    add(library, "LINKKEY1", str(elsewhere), link_mode=2)

    ok, target = download(library, "LINKKEY1")

    assert ok
    assert target.read_bytes() == b"linked"


@pytest.mark.parametrize(
    "key, path",
    [
        ("MISSING1", "storage:gone.pdf"),
        ("RELATIV1", "attachments:papers/a.pdf"),
        ("ESCAPE01", "storage:../../outside.pdf"),
        ("NOPATH01", ""),
    ],
)
def test_a_file_that_cannot_be_read_returns_false_and_writes_nothing(library, key, path):
    (library / "outside.pdf").write_bytes(b"secret")
    add(library, key, path)

    ok, target = download(library, key)

    assert not ok
    assert not target.exists()


def test_an_unknown_key_returns_false(library):
    ok, target = download(library, "NOSUCHKEY")

    assert not ok
    assert not target.exists()
