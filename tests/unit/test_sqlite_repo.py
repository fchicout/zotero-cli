import os
import sqlite3
import tempfile

import pytest

from zotero_cli.core.models import ZoteroQuery
from zotero_cli.infra.sqlite_repo import ConfigurationError, SqliteZoteroGateway


@pytest.fixture
def mock_db():
    """
    Schema matches a real Zotero Desktop zotero.sqlite exactly (verified
    against an actual local Desktop database - see Issue #174): items has no
    parentItemID column (attachment/note parent linkage lives on
    itemAttachments/itemNotes instead), collections has collectionName +
    parentCollectionID directly (no collectionData table), and creators has
    firstName/lastName directly (no creatorData table). A prior version of
    this fixture baked in the wrong schema, which the production code copied
    -- so tests and implementation drifted together instead of one catching
    the other.
    """
    fd, path = tempfile.mkstemp()
    conn = sqlite3.connect(path)

    # Setup Zotero Schema
    conn.executescript("""
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER, itemTypeID INTEGER, dateAdded TIMESTAMP DEFAULT CURRENT_TIMESTAMP, dateModified TIMESTAMP DEFAULT CURRENT_TIMESTAMP, clientDateModified TIMESTAMP DEFAULT CURRENT_TIMESTAMP, synced INTEGER DEFAULT 1);
        CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, linkMode INTEGER, contentType TEXT, path TEXT);
        CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, note TEXT, title TEXT);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT, fieldMode INTEGER);
        CREATE TABLE creatorTypes (creatorTypeID INTEGER PRIMARY KEY, creatorType TEXT);
        CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER);
        CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, key TEXT, collectionName TEXT, parentCollectionID INTEGER);
        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
        CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY, dateDeleted TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

        INSERT INTO itemTypes VALUES (1, 'journalArticle'), (2, 'attachment'), (3, 'note');
        INSERT INTO items (itemID, key, version, libraryID, itemTypeID) VALUES (1, 'ITEMKEY1', 1, 0, 1);
        INSERT INTO items (itemID, key, version, libraryID, itemTypeID) VALUES (2, 'ITEMKEY2', 1, 0, 1);
        INSERT INTO items (itemID, key, version, libraryID, itemTypeID) VALUES (3, 'ITEMKEY3', 1, 0, 2);
        INSERT INTO items (itemID, key, version, libraryID, itemTypeID) VALUES (4, 'ITEMKEY4', 1, 0, 3);
        INSERT INTO itemAttachments (itemID, parentItemID) VALUES (3, 2);
        INSERT INTO itemNotes (itemID, parentItemID) VALUES (4, 2);
        INSERT INTO fields VALUES (1, 'title'), (2, 'abstractNote'), (3, 'date'), (4, 'DOI'), (5, 'url'), (6, 'extra');
        INSERT INTO itemData VALUES (1, 1, 1), (2, 1, 2), (3, 1, 3);
        INSERT INTO itemDataValues VALUES (1, 'Test Title'), (2, 'Orphan Parent Title'), (3, 'Orphan Attachment');

        INSERT INTO creators (creatorID, firstName, lastName, fieldMode) VALUES (1, 'Jane', 'Doe', 0);
        INSERT INTO creatorTypes VALUES (1, 'author');
        INSERT INTO itemCreators VALUES (1, 1, 1, 0);

        INSERT INTO collections (collectionID, key, collectionName, parentCollectionID) VALUES (1, 'COLKEY1', 'Test Collection', NULL);
        INSERT INTO collections (collectionID, key, collectionName, parentCollectionID) VALUES (2, 'COLKEY2', 'Child Collection', 1);
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

    # ITEMKEY1, ITEMKEY2, ITEMKEY3 (attachment child), ITEMKEY4 (note child)
    assert len(items) == 4
    assert items[0].key == "ITEMKEY1"
    assert items[0].title == "Test Title"

    # Regression for Issue #174: creators must resolve via creators.firstName/
    # lastName directly -- the real schema has no separate creatorData table.
    assert items[0].authors == ["Jane Doe"]


def test_sqlite_read_items_issues_constant_query_count(mock_db):
    """Regression test for Issue #270: _fetch_items_with_filter must batch
    the creators/collections/tags lookups (IN (...) over all item IDs)
    instead of issuing 3 extra queries per row -- query count should stay
    flat as the result set grows, not scale linearly with item count."""
    gateway = SqliteZoteroGateway(mock_db)

    queries: list[str] = []
    orig_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        conn = orig_connect(*args, **kwargs)
        conn.set_trace_callback(queries.append)
        return conn

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sqlite3, "connect", counting_connect)
        items = list(gateway.search_items(ZoteroQuery()))

    assert len(items) == 4
    # 1 item query + 3 batched lookups (creators/collections/tags) regardless
    # of the 4-item result set -- previously this was 1 + 3*4 = 13.
    select_queries = [q for q in queries if q.strip().upper().startswith("SELECT")]
    assert len(select_queries) == 4


def test_sqlite_item_parent_key_resolves_via_attachments_and_notes(mock_db):
    """Regression test for Issue #174: parentKey must be resolved via
    itemAttachments/itemNotes -- the real schema has no items.parentItemID
    column at all."""
    gateway = SqliteZoteroGateway(mock_db)
    items = {i.key: i for i in gateway.search_items(ZoteroQuery())}

    assert items["ITEMKEY3"].parent_item == "ITEMKEY2"  # attachment child
    assert items["ITEMKEY4"].parent_item == "ITEMKEY2"  # note child
    assert items["ITEMKEY2"].parent_item is None or items["ITEMKEY2"].parent_item == ""


def test_sqlite_get_item_children(mock_db):
    """Regression test for Issue #174: get_item_children must find children
    via itemAttachments/itemNotes, not a nonexistent items.parentItemID."""
    gateway = SqliteZoteroGateway(mock_db)
    children = {c["key"] for c in gateway.get_item_children("ITEMKEY2")}
    assert children == {"ITEMKEY3", "ITEMKEY4"}
    assert gateway.get_item_children("ITEMKEY1") == []


def test_sqlite_read_collections(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    cols = {c["key"]: c for c in gateway.get_all_collections()}

    assert len(cols) == 2
    assert cols["COLKEY1"]["data"]["name"] == "Test Collection"
    assert cols["COLKEY1"]["data"]["parentCollection"] is None

    # Regression for Issue #174: parentCollectionID (an integer FK) must
    # resolve to the parent's key string, matching ZoteroAPIClient's shape --
    # the real schema has no collectionData table or parentCollection column.
    assert cols["COLKEY2"]["data"]["name"] == "Child Collection"
    assert cols["COLKEY2"]["data"]["parentCollection"] == "COLKEY1"

    col = gateway.get_collection("COLKEY2")
    assert col is not None
    assert col["data"]["parentCollection"] == "COLKEY1"


def test_sqlite_collections_include_meta_num_items(mock_db):
    """Regression test for Issue #322: offline collections must carry the
    same `meta.numItems` envelope the Zotero Web API returns - without it,
    `collection list --offline` crashed with KeyError: 'meta'."""
    gateway = SqliteZoteroGateway(mock_db)
    cols = {c["key"]: c for c in gateway.get_all_collections()}

    assert cols["COLKEY1"]["meta"]["numItems"] == 1  # ITEMKEY1
    assert cols["COLKEY2"]["meta"]["numItems"] == 0

    col = gateway.get_collection("COLKEY1")
    assert col is not None
    assert col["meta"]["numItems"] == 1


def test_sqlite_collection_num_items_excludes_trashed_items(mock_db):
    """Trashed items don't count toward a collection's size, matching the
    Web API's numItems."""
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO deletedItems (itemID) VALUES (1)")  # ITEMKEY1
    conn.commit()
    conn.close()

    gateway = SqliteZoteroGateway(mock_db)
    cols = {c["key"]: c for c in gateway.get_all_collections()}

    assert cols["COLKEY1"]["meta"]["numItems"] == 0


@pytest.mark.parametrize("table", [False, True])
def test_offline_collection_list_renders_without_error(mock_db, capsys, table):
    """Regression test for Issue #322, end to end: `collection list` (tree
    and --table) driven by a real SqliteZoteroGateway must render the
    offline hierarchy with item counts instead of crashing."""
    import argparse
    from unittest.mock import patch

    from zotero_cli.cli.commands.collection_cmd import CollectionCommand

    gateway = SqliteZoteroGateway(mock_db)
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway):
        CollectionCommand().execute(argparse.Namespace(verb="list", table=table, user=False))

    out = capsys.readouterr().out
    assert "Test Collection" in out
    assert "Child Collection" in out


def test_sqlite_orphan_items(mock_db):
    gateway = SqliteZoteroGateway(mock_db)

    # Without top_only: ITEMKEY2, ITEMKEY3, ITEMKEY4 (ITEMKEY1 is in a collection)
    orphans = list(gateway.get_orphan_items(top_only=False))
    assert len(orphans) == 3
    keys = {o.key for o in orphans}
    assert keys == {"ITEMKEY2", "ITEMKEY3", "ITEMKEY4"}

    # With top_only: only ITEMKEY2 -- ITEMKEY3/ITEMKEY4 are children (via
    # itemAttachments/itemNotes) of ITEMKEY2, not top-level themselves.
    top_orphans = list(gateway.get_orphan_items(top_only=True))
    assert len(top_orphans) == 1
    assert top_orphans[0].key == "ITEMKEY2"


def test_sqlite_get_trash_items(mock_db):
    """Regression test for Issue #140: ZoteroGateway.get_trash_items() must
    be implemented on the offline SqliteZoteroGateway too, not just the
    live ZoteroAPIClient."""
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO deletedItems (itemID) VALUES (2)")  # ITEMKEY2
    conn.commit()
    conn.close()

    gateway = SqliteZoteroGateway(mock_db)

    trashed = list(gateway.get_trash_items())
    assert len(trashed) == 1
    assert trashed[0].key == "ITEMKEY2"

    # Everything else must still exclude the trashed item, as before.
    all_items = list(gateway.search_items(ZoteroQuery()))
    assert {i.key for i in all_items} == {"ITEMKEY1", "ITEMKEY3", "ITEMKEY4"}


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
    # Item 1 is a journalArticle (top-level).
    # Item 2 is a journalArticle (top-level).
    # Item 3 is an attachment, a child of item 2 via itemAttachments.
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

    # With top_only: should only return ITEMKEY1 because ITEMKEY3 is a child (via itemAttachments) so it's not top-level
    top_items = list(gateway.get_items_in_collection("COLKEY1", top_only=True))
    assert len(top_items) == 1
    assert top_items[0].key == "ITEMKEY1"


def test_sqlite_write_fails(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    with pytest.raises(ConfigurationError) as excinfo:
        gateway.create_collection("New Col")
    assert "read-only" in str(excinfo.value)


def test_sqlite_gateway_warns_about_unscoped_library_access(mock_db, capsys, caplog):
    """Regression test for Issue #291: SqliteZoteroGateway queries every
    library in the local zotero.sqlite with no library_id filter - must
    warn loudly at construction time (stderr + logger.warning) rather
    than silently risking a wrong answer across multiple synced
    libraries."""
    import logging

    with caplog.at_level(logging.WARNING):
        SqliteZoteroGateway(mock_db)

    err = capsys.readouterr().err
    assert "offline" in err.lower()
    assert "entire local" in err.lower()
    assert any("entire local" in r.message.lower() for r in caplog.records)


def test_sqlite_shadow_copy(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    # Trigger shadow copy
    gateway.get_all_collections()
    assert gateway._temp_db_path is not None
    assert os.path.exists(gateway._temp_db_path)
    assert gateway._temp_db_path != mock_db


def test_sqlite_shadow_copy_path_is_not_pid_predictable(mock_db):
    """Issue #240: the shadow-copy path was previously a fully
    deterministic f"zotero_cli_shadow_{os.getpid()}.sqlite" - guessable
    since PID space is bounded/reused - letting a local attacker on a
    shared host pre-plant a symlink at that path. It now lives in a
    randomly named tempfile.mkdtemp() directory."""
    gateway = SqliteZoteroGateway(mock_db)
    gateway.get_all_collections()

    assert gateway._temp_db_path is not None
    temp_dir = os.path.basename(os.path.dirname(gateway._temp_db_path))
    assert temp_dir.startswith("zotero_cli_shadow_")
    assert temp_dir != f"zotero_cli_shadow_{os.getpid()}"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_sqlite_shadow_copy_is_private_even_if_source_is_world_readable(mock_db):
    """The shadow copy is the user's whole Zotero database: it must not
    inherit the source file's (typically 0644) mode, and its directory
    must be private too."""
    os.chmod(mock_db, 0o644)
    gateway = SqliteZoteroGateway(mock_db)
    gateway.get_all_collections()

    assert gateway._temp_db_path is not None
    assert os.stat(gateway._temp_db_path).st_mode & 0o777 == 0o600
    assert os.stat(os.path.dirname(gateway._temp_db_path)).st_mode & 0o777 == 0o700


def test_sqlite_shadow_copy_directory_is_removed_with_the_gateway(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    gateway.get_all_collections()
    assert gateway._temp_dir is not None
    temp_dir = gateway._temp_dir

    gateway.__del__()

    assert not os.path.exists(temp_dir)


def test_gateway_factory_offline(mock_db, monkeypatch):
    from zotero_cli.core.config import ZoteroConfig
    from zotero_cli.infra.factory import GatewayFactory

    config = ZoteroConfig(database_path=mock_db)

    # Test explicit offline=True
    gateway = GatewayFactory.get_zotero_gateway(config=config, offline=True)
    assert isinstance(gateway, SqliteZoteroGateway)

    # Test the process-wide --offline flag (Issue #363)
    monkeypatch.setattr("zotero_cli.core.runtime._offline", True)
    gateway = GatewayFactory.get_zotero_gateway(config=config)
    assert isinstance(gateway, SqliteZoteroGateway)


def test_gateway_factory_offline_no_db(monkeypatch):
    from zotero_cli.core.config import ZoteroConfig
    from zotero_cli.core.exceptions import ConfigurationError
    from zotero_cli.infra.factory import GatewayFactory

    config = ZoteroConfig(database_path=None)

    with pytest.raises(ConfigurationError):
        GatewayFactory.get_zotero_gateway(config=config, offline=True)


def test_sqlite_items_include_venue_fields_only_when_present(mock_db):
    """Issue #323: `item list --wide`/`--fields venue` needs the venue
    fields offline too. Like the Web API, a field appears in the item data
    only when the item actually has it."""
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO fields VALUES (7, 'publicationTitle')")
    conn.execute("INSERT INTO itemDataValues VALUES (4, 'Journal of Tests')")
    conn.execute("INSERT INTO itemData VALUES (1, 7, 4)")  # ITEMKEY1
    conn.commit()
    conn.close()

    gateway = SqliteZoteroGateway(mock_db)
    items = {i.key: i for i in gateway.search_items(ZoteroQuery())}

    assert items["ITEMKEY1"].raw_data["data"]["publicationTitle"] == "Journal of Tests"
    assert "publicationTitle" not in items["ITEMKEY2"].raw_data["data"]
    assert "proceedingsTitle" not in items["ITEMKEY1"].raw_data["data"]
