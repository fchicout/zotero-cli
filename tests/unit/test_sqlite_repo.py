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
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER, itemTypeID INTEGER, parentItemID INTEGER);
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

        INSERT INTO itemTypes VALUES (1, 'journalArticle');
        INSERT INTO items VALUES (1, 'ITEMKEY1', 1, 0, 1, NULL);
        INSERT INTO fields VALUES (1, 'title'), (2, 'abstractNote'), (3, 'date'), (4, 'DOI'), (5, 'url'), (6, 'extra');
        INSERT INTO itemData VALUES (1, 1, 1);
        INSERT INTO itemDataValues VALUES (1, 'Test Title');
        
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

    assert len(items) == 1
    assert items[0].key == 'ITEMKEY1'
    assert items[0].title == 'Test Title'

def test_sqlite_read_collections(mock_db):
    gateway = SqliteZoteroGateway(mock_db)
    cols = gateway.get_all_collections()

    assert len(cols) == 1
    assert cols[0]['key'] == 'COLKEY1'
    assert cols[0]['data']['name'] == 'Test Collection'

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
    from zotero_cli.infra.factory import GatewayFactory

    config = ZoteroConfig(database_path=None)

    with pytest.raises(SystemExit):
        GatewayFactory.get_zotero_gateway(config=config, offline=True)
