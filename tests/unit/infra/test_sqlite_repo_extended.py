import sqlite3

import pytest

from zotero_cli.core.models import Job, ResearchPaper
from zotero_cli.infra.sqlite_repo import (
    ConfigurationError,
    SqliteJobRepository,
    SqliteZoteroGateway,
)


@pytest.fixture
def sample_zotero_db(tmp_path):
    db_path = str(tmp_path / "zotero.sqlite")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE collections (key TEXT, parentCollection TEXT, collectionID INTEGER)")
    conn.execute("CREATE TABLE collectionData (collectionID INTEGER, name TEXT)")
    conn.execute("INSERT INTO collections VALUES ('COL1', NULL, 1)")
    conn.execute("INSERT INTO collectionData VALUES (1, 'Test Collection')")
    # Add items tables
    conn.execute(
        "CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER, itemTypeID INTEGER, parentItemID INTEGER)"
    )
    conn.execute("CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT)")
    conn.execute("CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER)")
    conn.execute("CREATE TABLE fields (fieldID INTEGER, fieldName TEXT)")
    conn.execute("CREATE TABLE itemDataValues (valueID INTEGER, value TEXT)")
    conn.execute("CREATE TABLE deletedItems (itemID INTEGER)")
    conn.execute(
        "CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER)"
    )
    conn.execute("CREATE TABLE creators (creatorID INTEGER, creatorDataID INTEGER)")
    conn.execute("CREATE TABLE creatorData (creatorDataID INTEGER, firstName TEXT, lastName TEXT)")
    conn.execute("CREATE TABLE creatorTypes (creatorTypeID INTEGER, creatorType TEXT)")
    conn.execute("CREATE TABLE collectionItems (itemID INTEGER, collectionID INTEGER)")
    conn.execute("CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER)")
    conn.execute("CREATE TABLE tags (tagID INTEGER, name TEXT)")
    conn.commit()
    conn.close()
    return db_path


def test_gateway_read_ops(sample_zotero_db):
    gateway = SqliteZoteroGateway(sample_zotero_db)
    # get_all_collections
    cols = gateway.get_all_collections()
    assert len(cols) == 1
    assert cols[0]["key"] == "COL1"
    # get_collection
    col = gateway.get_collection("COL1")
    assert col is not None
    assert col["data"]["name"] == "Test Collection"
    assert gateway.get_collection("MISSING") is None
    # get_collection_id_by_name
    assert gateway.get_collection_id_by_name("Test Collection") == "COL1"
    assert gateway.get_collection_id_by_name("Unknown") is None


def test_gateway_forbidden_writes(sample_zotero_db):
    gateway = SqliteZoteroGateway(sample_zotero_db)
    paper = ResearchPaper(title="T", abstract="", doi="10.123")
    with pytest.raises(ConfigurationError):
        gateway.create_item(paper, "C1")
    with pytest.raises(ConfigurationError):
        gateway.create_generic_item({})
    with pytest.raises(ConfigurationError):
        gateway.update_item("K1", 1, {})
    with pytest.raises(ConfigurationError):
        gateway.delete_item("K1", 1)
    with pytest.raises(ConfigurationError):
        gateway.create_collection("New")
    with pytest.raises(ConfigurationError):
        gateway.delete_collection("K1", 1)
    with pytest.raises(ConfigurationError):
        gateway.rename_collection("K1", 1, "New")
    with pytest.raises(ConfigurationError):
        gateway.add_tags("K1", ["T1"])
    with pytest.raises(ConfigurationError):
        gateway.delete_tags(["T1"], 1)
    with pytest.raises(ConfigurationError):
        gateway.create_note("K1", "Note")
    with pytest.raises(ConfigurationError):
        gateway.update_note("K1", 1, "Note")
    with pytest.raises(ConfigurationError):
        gateway.update_item_metadata("K1", 1, {})
    with pytest.raises(ConfigurationError):
        gateway.upload_attachment("K1", "path")
    with pytest.raises(ConfigurationError):
        gateway.download_attachment("K1", "path")
    with pytest.raises(ConfigurationError):
        gateway.update_attachment_link("K1", 1, "path")


def test_gateway_read_tags(sample_zotero_db):
    gateway = SqliteZoteroGateway(sample_zotero_db)
    conn = sqlite3.connect(sample_zotero_db)
    conn.execute("INSERT INTO items VALUES (1, 'K1', 1, 1, 1, NULL)")
    conn.execute("INSERT INTO itemTypes VALUES (1, 'journalArticle')")
    conn.execute("INSERT INTO tags VALUES (1, 'Tag1')")
    conn.execute("INSERT INTO itemTags VALUES (1, 1)")
    conn.commit()
    conn.close()
    assert "Tag1" in gateway.get_tags()
    assert "Tag1" in gateway.get_tags_for_item("K1")
    items = list(gateway.get_items_by_tag("Tag1"))
    assert len(items) == 1
    assert items[0].key == "K1"


def test_job_repo_list_jobs(tmp_path):
    db_path = str(tmp_path / "jobs.sqlite")
    repo = SqliteJobRepository(db_path)
    repo.enqueue(Job(item_key="K1", task_type="t1", payload={}))
    repo.enqueue(Job(item_key="K2", task_type="t2", payload={}))
    assert len(repo.list_jobs()) == 2
    assert len(repo.list_jobs(task_type="t1")) == 1
    assert repo.list_jobs(task_type="t1")[0].item_key == "K1"


def test_gateway_missing_db():
    with pytest.raises(ConfigurationError, match="Zotero database not found"):
        SqliteZoteroGateway("/non/existent/path.sqlite")


def test_gateway_verify_credentials(sample_zotero_db):
    gateway = SqliteZoteroGateway(sample_zotero_db)
    assert gateway.verify_credentials() is True
    gateway.original_db_path = "/non/existent"
    assert gateway.verify_credentials() is False
