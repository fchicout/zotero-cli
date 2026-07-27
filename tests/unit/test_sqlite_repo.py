import os
import sqlite3
import tempfile

import pytest

from zotero_cli.core.models import ZoteroQuery
from zotero_cli.infra.sqlite_repo import ConfigurationError, SqliteZoteroGateway


@pytest.fixture
def mock_db():
    fd, path = tempfile.mkstemp()
    conn = sqlite3.connect(path)

    # Setup Zotero Schema
    conn.executescript("""
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER, itemTypeID INTEGER, parentItemID INTEGER, dateModified TIMESTAMP DEFAULT CURRENT_TIMESTAMP, clientDateModified TIMESTAMP DEFAULT CURRENT_TIMESTAMP, synced INTEGER DEFAULT 1);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, creatorDataID INTEGER);
        CREATE TABLE creatorData (creatorDataID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT);
        CREATE TABLE creatorTypes (creatorTypeID INTEGER PRIMARY KEY, creatorType TEXT);
        CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER);
        CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, key TEXT, parentCollection TEXT);
        CREATE TABLE collectionData (collectionID INTEGER, name TEXT);
        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
        CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);

        INSERT INTO itemTypes VALUES (1, 'journalArticle'), (2, 'attachment');
        INSERT INTO items (itemID, key, version, libraryID, itemTypeID, parentItemID) VALUES (1, 'ITEMKEY1', 1, 0, 1, NULL);
        INSERT INTO items (itemID, key, version, libraryID, itemTypeID, parentItemID) VALUES (2, 'ITEMKEY2', 1, 0, 1, NULL);
        INSERT INTO items (itemID, key, version, libraryID, itemTypeID, parentItemID) VALUES (3, 'ITEMKEY3', 1, 0, 2, 2);
        INSERT INTO fields VALUES (1, 'title'), (2, 'abstractNote'), (3, 'date'), (4, 'DOI'), (5, 'url'), (6, 'extra');
        INSERT INTO itemData VALUES (1, 1, 1), (2, 1, 2), (3, 1, 3);
        INSERT INTO itemDataValues VALUES (1, 'Test Title'), (2, 'Orphan Parent Title'), (3, 'Orphan Attachment');

        INSERT INTO collections VALUES (1, 'COLKEY1', NULL);
        INSERT INTO collectionData VALUES (1, 'Test Collection');
        INSERT INTO collectionItems VALUES (1, 1);
    """)
    conn.commit()
    conn.close()
    yield path
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)


def test_sqlite_read_items(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    items = list(gateway.search_items(ZoteroQuery()))

    # ITEMKEY1, ITEMKEY2, ITEMKEY3
    assert len(items) == 3
    assert items[0].key == "ITEMKEY1"
    assert items[0].title == "Test Title"


def test_sqlite_read_collections(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    cols = gateway.get_all_collections()

    assert len(cols) == 1
    assert cols[0]["key"] == "COLKEY1"
    assert cols[0]["data"]["name"] == "Test Collection"


def test_sqlite_orphan_items(mock_db):
    gateway = SqliteZoteroGateway(mock_db)

    # Without top_only: should return ITEMKEY2 and ITEMKEY3 (since ITEMKEY1 is in a collection)
    orphans = list(gateway.get_orphan_items(top_only=False))
    assert len(orphans) == 2
    keys = {o.key for o in orphans}
    assert keys == {"ITEMKEY2", "ITEMKEY3"}

    # With top_only: should only return ITEMKEY2 because ITEMKEY3 has ITEMKEY2 as parent
    top_orphans = list(gateway.get_orphan_items(top_only=True))
    assert len(top_orphans) == 1
    assert top_orphans[0].key == "ITEMKEY2"


def test_sqlite_get_trash_items(mock_db):
    """Regression test for Issue #140: ZoteroGateway.get_trash_items() must
    be implemented on the offline SqliteZoteroGateway too, not just the
    live ZoteroAPIClient."""
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO deletedItems VALUES (2)")  # ITEMKEY2
    conn.commit()
    conn.close()

    gateway = SqliteZoteroGateway(mock_db)

    trashed = list(gateway.get_trash_items())
    assert len(trashed) == 1
    assert trashed[0].key == "ITEMKEY2"

    # Everything else must still exclude the trashed item, as before.
    all_items = list(gateway.search_items(ZoteroQuery()))
    assert {i.key for i in all_items} == {"ITEMKEY1", "ITEMKEY3"}


def test_sqlite_trash_and_restore_item(mock_db):
    """Regression test for Issue #145: item trash/restore in --offline mode
    must write the same SQL Zotero Desktop itself writes (confirmed against
    Desktop's actual client source): bump dateModified/clientDateModified,
    mark the row dirty (synced=0) so Desktop's next sync picks it up, and
    add/remove the deletedItems row. version must be left untouched."""
    gateway = SqliteZoteroGateway(mock_db)

    assert gateway.trash_item("ITEMKEY1") is True
    assert gateway.trash_item("DOES_NOT_EXIST") is False

    # Verify against a *fresh* gateway instance, since the shadow-copy read
    # strategy means a stale gateway's own reads wouldn't reflect a write
    # made through its write connection -- but real CLI usage always
    # constructs a new gateway per invocation, so this is the honest check.
    fresh = SqliteZoteroGateway(mock_db)
    trashed = list(fresh.get_trash_items())
    assert {i.key for i in trashed} == {"ITEMKEY1"}

    conn = sqlite3.connect(mock_db)
    row = conn.execute(
        "SELECT synced, version FROM items WHERE key = 'ITEMKEY1'"
    ).fetchone()
    conn.close()
    assert row[0] == 0  # synced=0, marked dirty for next real sync
    assert row[1] == 1  # version untouched -- only the server bumps it

    assert gateway.restore_item("ITEMKEY1") is True
    assert gateway.restore_item("DOES_NOT_EXIST") is False

    fresh2 = SqliteZoteroGateway(mock_db)
    assert list(fresh2.get_trash_items()) == []


def test_sqlite_trash_writes_to_real_file_not_shadow_copy(mock_db):
    """The shadow-copy strategy (_get_connection) exists precisely so reads
    never lock/touch the live file -- but that means it must NOT be reused
    for writes, since writes to a throwaway temp copy would be silently
    lost. This proves trash_item() writes to original_db_path directly."""
    gateway = SqliteZoteroGateway(mock_db)
    # Force the shadow copy to be created first.
    gateway.get_all_collections()
    assert gateway._temp_db_path is not None

    gateway.trash_item("ITEMKEY1")

    conn = sqlite3.connect(mock_db)  # the real file, not the shadow copy
    count = conn.execute("SELECT COUNT(*) FROM deletedItems WHERE itemID = 1").fetchone()[0]
    conn.close()
    assert count == 1


def test_sqlite_collection_items_top_only(mock_db):
    # Setup: Put item 1 and item 3 in collection 1.
    # Note: item 3 has parentItemID = 2. But parentItemID 2 is NOT in the collection or is in the collection.
    # Let's insert a direct test. In mock_db setup:
    # Item 1 is JOURNALARTICLE (parent = NULL)
    # Item 2 is JOURNALARTICLE (parent = NULL)
    # Item 3 is ATTACHMENT (parent = 2)
    # Collection Items has (1, 1). Let's add (1, 3) to test it.
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO collectionItems VALUES (1, 3)")
    conn.commit()
    conn.close()

    gateway = SqliteZoteroGateway(mock_db)

    # Without top_only: should return both ITEMKEY1 and ITEMKEY3 (since both are in collection 1)
    items = list(gateway.get_items_in_collection("COLKEY1", top_only=False))
    assert len(items) == 2
    keys = {item.key for item in items}
    assert keys == {"ITEMKEY1", "ITEMKEY3"}

    # With top_only: should only return ITEMKEY1 because ITEMKEY3 has parentItemID = 2 (so it's not a top-level item)
    top_items = list(gateway.get_items_in_collection("COLKEY1", top_only=True))
    assert len(top_items) == 1
    assert top_items[0].key == "ITEMKEY1"


def test_sqlite_write_fails(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    with pytest.raises(ConfigurationError) as excinfo:
        gateway.create_collection("New Col")
    assert "read-only" in str(excinfo.value)


def test_sqlite_shadow_copy(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    # Trigger shadow copy
    gateway.get_all_collections()
    assert gateway._temp_db_path is not None
    assert os.path.exists(gateway._temp_db_path)
    assert gateway._temp_db_path != mock_db


def test_gateway_factory_offline(mock_db, monkeypatch):
    from zotero_cli.core.config import ZoteroConfig
    from zotero_cli.infra.factory import GatewayFactory

    config = ZoteroConfig(database_path=mock_db)

    # Test explicit offline=True
    gateway = GatewayFactory.get_zotero_gateway(config=config, offline=True)
    assert isinstance(gateway, SqliteZoteroGateway)

    # Test global OFFLINE_MODE
    monkeypatch.setattr("zotero_cli.cli.main.OFFLINE_MODE", True, raising=False)
    gateway = GatewayFactory.get_zotero_gateway(config=config)
    assert isinstance(gateway, SqliteZoteroGateway)


def test_gateway_factory_offline_no_db(monkeypatch):
    from zotero_cli.core.config import ZoteroConfig
    from zotero_cli.core.exceptions import ConfigurationError
    from zotero_cli.infra.factory import GatewayFactory

    config = ZoteroConfig(database_path=None)

    with pytest.raises(ConfigurationError):
        GatewayFactory.get_zotero_gateway(config=config, offline=True)
