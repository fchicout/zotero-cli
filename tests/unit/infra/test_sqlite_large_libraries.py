"""Issues #422/#423: offline reads bound one "?" per matched item, so a
library past SQLite's bound-variable limit (32,766 in most builds) crashed
with "too many SQL variables"; Zotero 7 annotation rows, listed as items,
pushed ordinary libraries past it."""

import sqlite3
from pathlib import Path
from typing import Iterator

import pytest

from zotero_cli.core.models import ZoteroQuery
from zotero_cli.infra import sqlite_repo
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

# The gateway's connections get this limit, so a few hundred items stand in
# for a 33k-row library whatever SQLite build runs the tests.
VARIABLE_LIMIT = 200
PAPERS = 300
HIGHLIGHTS_PER_PAPER = 4

SCHEMA = """
    CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
    CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER,
        libraryID INTEGER, itemTypeID INTEGER);
    CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INTEGER,
        linkMode INTEGER, contentType TEXT, path TEXT);
    CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, note TEXT,
        title TEXT);
    CREATE TABLE itemAnnotations (itemID INTEGER PRIMARY KEY, parentItemID INTEGER,
        type INTEGER, text TEXT);
    CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
    CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER,
        PRIMARY KEY (itemID, fieldID));
    CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
    CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT,
        fieldMode INTEGER);
    CREATE TABLE creatorTypes (creatorTypeID INTEGER PRIMARY KEY, creatorType TEXT);
    CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER,
        orderIndex INTEGER);
    CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, key TEXT,
        collectionName TEXT, parentCollectionID INTEGER);
    CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
    CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
    CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
    CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);
    CREATE INDEX itemCreators_item ON itemCreators(itemID);
    CREATE INDEX collectionItems_item ON collectionItems(itemID);
    CREATE INDEX itemTags_item ON itemTags(itemID);
    INSERT INTO itemTypes VALUES (1, 'journalArticle'), (2, 'attachment'), (3, 'annotation');
    INSERT INTO fields VALUES (1, 'title'), (2, 'DOI');
    INSERT INTO creators VALUES (1, 'Jane', 'Doe', 0);
    INSERT INTO creatorTypes VALUES (1, 'author');
    INSERT INTO collections VALUES (1, 'COLKEY1', 'Big', NULL);
    INSERT INTO tags VALUES (1, 'reviewed');
"""


def _build(path: Path, analyze: bool) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    next_id = 1
    for paper in range(PAPERS):
        paper_id, pdf_id = next_id, next_id + 1
        next_id += 2
        conn.execute("INSERT INTO items VALUES (?, ?, 1, 1, 1)", (paper_id, f"P{paper:07d}"))
        conn.execute("INSERT INTO itemDataValues VALUES (?, ?)", (paper_id * 2, f"Paper {paper}"))
        conn.execute("INSERT INTO itemData VALUES (?, 1, ?)", (paper_id, paper_id * 2))
        conn.execute(
            "INSERT INTO itemDataValues VALUES (?, ?)", (paper_id * 2 + 1, f"10.1/{paper}")
        )
        conn.execute("INSERT INTO itemData VALUES (?, 2, ?)", (paper_id, paper_id * 2 + 1))
        conn.execute("INSERT INTO itemCreators VALUES (?, 1, 1, 0)", (paper_id,))
        conn.execute("INSERT INTO collectionItems VALUES (1, ?)", (paper_id,))
        conn.execute("INSERT INTO itemTags VALUES (?, 1)", (paper_id,))
        conn.execute("INSERT INTO items VALUES (?, ?, 1, 1, 2)", (pdf_id, f"A{paper:07d}"))
        conn.execute(
            "INSERT INTO itemAttachments VALUES (?, ?, 0, 'application/pdf', NULL)",
            (pdf_id, paper_id),
        )
        for _ in range(HIGHLIGHTS_PER_PAPER):
            conn.execute("INSERT INTO items VALUES (?, ?, 1, 1, 3)", (next_id, f"N{next_id:07d}"))
            conn.execute(
                "INSERT INTO itemAnnotations VALUES (?, ?, 1, 'highlight')", (next_id, pdf_id)
            )
            next_id += 1
    if analyze:
        conn.execute("ANALYZE")
    conn.commit()
    conn.close()


@pytest.fixture(params=[False, True], ids=["no-stats", "analyzed"])
def gateway(request, tmp_path, monkeypatch) -> Iterator[SqliteZoteroGateway]:
    db = tmp_path / "zotero.sqlite"
    _build(db, analyze=request.param)

    real_connect = sqlite3.connect

    def limited_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, VARIABLE_LIMIT)
        return conn

    monkeypatch.setattr(sqlite_repo.sqlite3, "connect", limited_connect)
    yield SqliteZoteroGateway(str(db))


def test_get_all_items_past_the_variable_limit(gateway):
    items = list(gateway.get_all_items())

    # papers + their PDFs; no annotation rows (Issue #423)
    assert len(items) == PAPERS * 2
    paper = next(i for i in items if i.key == "P0000299")
    assert paper.tags == ["reviewed"]
    assert paper.collections == ["COLKEY1"]
    assert paper.raw_data["data"]["creators"][0]["lastName"] == "Doe"


def test_search_items_past_the_variable_limit(gateway):
    assert len(list(gateway.search_items(ZoteroQuery(q="paper")))) == PAPERS
    assert len(list(gateway.search_items(ZoteroQuery(item_type="journalArticle")))) == PAPERS


def test_get_items_by_doi_past_the_variable_limit(gateway):
    assert [i.key for i in gateway.get_items_by_doi("10.1/42")] == ["P0000042"]


def test_large_collection_past_the_variable_limit(gateway):
    items = list(gateway.get_items_in_collection("COLKEY1"))

    assert len(items) == PAPERS
    assert all(i.collections == ["COLKEY1"] for i in items)


def test_annotations_are_not_listed_as_items(gateway):
    types = {i.item_type for i in gateway.get_all_items()}

    assert "annotation" not in types
    assert list(gateway.search_items(ZoteroQuery(item_type="annotation"))) == []
