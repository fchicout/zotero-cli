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
    """Schema matches a real Zotero Desktop zotero.sqlite exactly (see Issue
    #174): no collectionData/creatorData tables, no items.parentItemID --
    parent linkage for attachments/notes lives on itemAttachments/itemNotes."""
    db_path = str(tmp_path / "zotero.sqlite")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE collections (key TEXT, collectionName TEXT, collectionID INTEGER, parentCollectionID INTEGER)"
    )
    conn.execute("INSERT INTO collections VALUES ('COL1', 'Test Collection', 1, NULL)")
    # Add items tables
    conn.execute(
        "CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER, itemTypeID INTEGER)"
    )
    conn.execute("CREATE TABLE itemAttachments (itemID INTEGER, parentItemID INTEGER)")
    conn.execute("CREATE TABLE itemNotes (itemID INTEGER, parentItemID INTEGER)")
    conn.execute("CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT)")
    conn.execute("CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER)")
    conn.execute("CREATE TABLE fields (fieldID INTEGER, fieldName TEXT)")
    conn.execute("CREATE TABLE itemDataValues (valueID INTEGER, value TEXT)")
    conn.execute("CREATE TABLE deletedItems (itemID INTEGER)")
    conn.execute(
        "CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER)"
    )
    conn.execute("CREATE TABLE creators (creatorID INTEGER, firstName TEXT, lastName TEXT)")
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
    conn.execute("INSERT INTO items VALUES (1, 'K1', 1, 1, 1)")
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


def test_gateway_read_item_by_key(sample_zotero_db):
    gateway = SqliteZoteroGateway(sample_zotero_db)
    conn = sqlite3.connect(sample_zotero_db)
    conn.execute("INSERT INTO items VALUES (1, 'K1', 3, 1, 1)")
    conn.execute("INSERT INTO itemTypes VALUES (1, 'journalArticle')")
    conn.execute("INSERT INTO fields VALUES (100, 'title')")
    conn.execute("INSERT INTO itemDataValues VALUES (200, 'Direct SQL Lookup')")
    conn.execute("INSERT INTO itemData VALUES (1, 100, 200)")
    conn.commit()
    conn.close()

    item = gateway.get_item("K1")

    assert item is not None
    assert item.key == "K1"
    assert item.version == 3
    assert item.title == "Direct SQL Lookup"
    assert gateway.get_item("MISSING") is None


def test_gateway_read_items_by_doi(sample_zotero_db):
    gateway = SqliteZoteroGateway(sample_zotero_db)
    conn = sqlite3.connect(sample_zotero_db)
    conn.execute("INSERT INTO items VALUES (1, 'K1', 1, 1, 1)")
    conn.execute("INSERT INTO itemTypes VALUES (1, 'journalArticle')")
    conn.execute("INSERT INTO fields VALUES (101, 'DOI')")
    conn.execute("INSERT INTO itemDataValues VALUES (201, '10.1234/example')")
    conn.execute("INSERT INTO itemData VALUES (1, 101, 201)")
    conn.commit()
    conn.close()

    items = list(gateway.get_items_by_doi("10.1234/example"))

    assert len(items) == 1
    assert items[0].key == "K1"
    assert items[0].doi == "10.1234/example"
    assert list(gateway.get_items_by_doi("10.9999/missing")) == []


def test_job_repo_list_jobs(tmp_path):
    db_path = str(tmp_path / "jobs.sqlite")
    repo = SqliteJobRepository(db_path)
    repo.enqueue(Job(item_key="K1", task_type="t1", payload={}))
    repo.enqueue(Job(item_key="K2", task_type="t2", payload={}))
    assert len(repo.list_jobs()) == 2
    assert len(repo.list_jobs(task_type="t1")) == 1
    assert repo.list_jobs(task_type="t1")[0].item_key == "K1"


def test_job_repo_uses_wal_journal_mode(tmp_path):
    db_path = str(tmp_path / "jobs.sqlite")
    SqliteJobRepository(db_path)

    conn = sqlite3.connect(db_path)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        conn.close()


def test_job_repo_library_id_scoping(tmp_path):
    db_path = str(tmp_path / "jobs.sqlite")
    repo = SqliteJobRepository(db_path)
    repo.enqueue(Job(item_key="A1", task_type="t1", payload={}, library_id="lib-A"))
    repo.enqueue(Job(item_key="B1", task_type="t1", payload={}, library_id="lib-B"))

    jobs_a = repo.list_jobs(library_id="lib-A")
    jobs_b = repo.list_jobs(library_id="lib-B")
    assert [j.item_key for j in jobs_a] == ["A1"]
    assert [j.item_key for j in jobs_b] == ["B1"]

    popped_a = repo.get_next_pending("t1", library_id="lib-A")
    assert popped_a is not None
    assert popped_a.item_key == "A1"
    assert repo.get_next_pending("t1", library_id="lib-A") is None


def test_job_repo_legacy_null_library_id_stays_visible(tmp_path):
    db_path = str(tmp_path / "jobs.sqlite")
    repo = SqliteJobRepository(db_path)
    repo.enqueue(Job(item_key="LEGACY", task_type="t1", payload={}))  # library_id=None

    assert "LEGACY" in [j.item_key for j in repo.list_jobs(library_id="lib-A")]
    popped = repo.get_next_pending("t1", library_id="lib-A")
    assert popped is not None
    assert popped.item_key == "LEGACY"


def test_job_repo_migrates_pre_existing_db_missing_library_id_column(tmp_path):
    """A jobs.sqlite created before Issue #150 has no library_id column at
    all; opening it must migrate the schema instead of crashing."""
    db_path = str(tmp_path / "jobs.sqlite")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key TEXT NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            next_retry_at TEXT,
            payload TEXT NOT NULL,
            last_error TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO jobs (item_key, task_type, status, attempts, payload) "
        "VALUES ('PRE', 't1', 'PENDING', 0, '{}')"
    )
    conn.commit()
    conn.close()

    repo = SqliteJobRepository(db_path)
    jobs = repo.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].item_key == "PRE"
    assert jobs[0].library_id is None


def test_gateway_missing_db():
    with pytest.raises(ConfigurationError, match="Zotero database not found"):
        SqliteZoteroGateway("/non/existent/path.sqlite")


def test_gateway_verify_credentials(sample_zotero_db):
    gateway = SqliteZoteroGateway(sample_zotero_db)
    assert gateway.verify_credentials() is True
    gateway.original_db_path = "/non/existent"
    assert gateway.verify_credentials() is False
