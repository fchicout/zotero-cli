"""Issue #417: offline `item trash`/`item restore` write to the live
zotero.sqlite. They now back it up first, scope the key to the configured
library, and refuse a key they can't attribute to one library."""

import os
import sqlite3
import stat

import pytest

from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

SCHEMA = """
    CREATE TABLE libraries (libraryID INTEGER PRIMARY KEY, type TEXT);
    CREATE TABLE groups (groupID INTEGER PRIMARY KEY, libraryID INTEGER);
    CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
    CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER,
        itemTypeID INTEGER, dateAdded TIMESTAMP, dateModified TIMESTAMP,
        clientDateModified TIMESTAMP, synced INTEGER DEFAULT 1);
    CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY, dateDeleted TIMESTAMP);
    INSERT INTO libraries VALUES (1, 'user'), (2, 'group');
    INSERT INTO groups VALUES (555, 2);
    INSERT INTO itemTypes VALUES (1, 'journalArticle');
    INSERT INTO items (itemID, key, version, libraryID, itemTypeID) VALUES
        (10, 'SHARED01', 1, 1, 1),   -- same key in the user library...
        (20, 'SHARED01', 1, 2, 1),   -- ...and in group 555
        (30, 'ONLYUSER', 1, 1, 1);
"""


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return str(path)


def _trashed(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return {r[0] for r in conn.execute("SELECT itemID FROM deletedItems")}
    finally:
        conn.close()


def test_group_library_scope_trashes_only_that_librarys_item(db):
    gateway = SqliteZoteroGateway(db, library_id="555", library_type="group")

    assert gateway.trash_item("SHARED01") is True
    assert _trashed(db) == {20}


def test_user_library_scope(db):
    gateway = SqliteZoteroGateway(db, library_id="999", library_type="user")

    assert gateway.trash_item("SHARED01") is True
    assert _trashed(db) == {10}


def test_a_key_in_another_library_is_not_found_in_scope(db):
    gateway = SqliteZoteroGateway(db, library_id="555", library_type="group")

    assert gateway.trash_item("ONLYUSER") is False
    assert _trashed(db) == set()


def test_unscoped_ambiguous_key_is_refused(db):
    gateway = SqliteZoteroGateway(db)

    with pytest.raises(RuntimeError, match="2 locally synced libraries"):
        gateway.trash_item("SHARED01")
    assert _trashed(db) == set()


def test_unscoped_unique_key_still_works(db):
    assert SqliteZoteroGateway(db).trash_item("ONLYUSER") is True
    assert _trashed(db) == {30}


def test_backup_is_taken_once_before_the_first_write(db, capsys):
    gateway = SqliteZoteroGateway(db, library_id="999", library_type="user")
    backup = db + ".zotero-cli-bak"

    gateway.trash_item("ONLYUSER")
    assert os.path.exists(backup)
    if os.name != "nt":
        assert stat.S_IMODE(os.stat(backup).st_mode) == 0o600
    # The backup is the state before the write.
    conn = sqlite3.connect(backup)
    try:
        assert conn.execute("SELECT COUNT(*) FROM deletedItems").fetchone()[0] == 0
    finally:
        conn.close()
    assert "Backed up zotero.sqlite" in capsys.readouterr().err

    first_mtime = os.stat(backup).st_mtime_ns
    gateway.restore_item("ONLYUSER")
    assert os.stat(backup).st_mtime_ns == first_mtime  # once per run


def test_no_backup_when_nothing_is_written(db):
    SqliteZoteroGateway(db, library_id="555", library_type="group").trash_item("MISSING1")
    assert not os.path.exists(db + ".zotero-cli-bak")
