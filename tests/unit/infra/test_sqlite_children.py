"""Offline children have the Web API's shape (Issue #437)."""

import json
import sqlite3

import pytest

from zotero_cli.core.services.sdb.sdb_service import SDBService
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

SCHEMA = """
CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER,
    itemTypeID INTEGER, dateAdded TEXT, dateModified TEXT);
CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, linkMode INTEGER,
    contentType TEXT, path TEXT);
CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, note TEXT, title TEXT);
CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);
INSERT INTO itemTypes VALUES (1, 'journalArticle'), (2, 'attachment'), (3, 'note');
INSERT INTO fields VALUES (1, 'title'), (2, 'url');
"""


def _decision(decision: str) -> str:
    body = {"sdb_version": "1.2", "phase": "title_abstract", "decision": decision}
    return f"<div>{json.dumps(body)}</div>"


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    rows = [
        (1, "PAPER001", 1), (2, "PAPER002", 1),
        (10, "NOTE0001", 3), (11, "PDF00001", 2), (12, "LINK0001", 2),
        (20, "NOTE0002", 3), (21, "GONE0001", 3),
    ]
    for item_id, key, type_id in rows:
        conn.execute(
            "INSERT INTO items VALUES (?, ?, 5, 1, ?, '2026-01-01 10:00:00', '2026-01-02 11:00:00')",
            (item_id, key, type_id),
        )
    conn.execute("INSERT INTO itemNotes VALUES (10, 1, ?, 'SDB')", (_decision("accepted"),))
    conn.execute("INSERT INTO itemNotes VALUES (20, 2, ?, 'SDB')", (_decision("rejected"),))
    conn.execute("INSERT INTO itemNotes VALUES (21, 2, ?, 'SDB')", (_decision("accepted"),))
    conn.execute("INSERT INTO deletedItems VALUES (21)")  # trashed: not a child
    conn.execute(
        "INSERT INTO itemAttachments VALUES (11, 1, 0, 'application/pdf', 'storage:paper.pdf')"
    )
    conn.execute("INSERT INTO itemAttachments VALUES (12, 1, 2, 'application/pdf', '/papers/x.pdf')")
    conn.execute("INSERT INTO itemDataValues VALUES (1, 'Full Text PDF')")
    conn.execute("INSERT INTO itemData VALUES (11, 1, 1)")
    conn.execute("INSERT INTO tags VALUES (1, 'sdb')")
    conn.execute("INSERT INTO itemTags VALUES (10, 1)")
    conn.commit()
    conn.close()
    return str(path)


def test_note_children_carry_the_note_body(db):
    children = SqliteZoteroGateway(db).get_item_children("PAPER001")
    note = next(c for c in children if c["key"] == "NOTE0001")
    assert note["version"] == 5
    assert note["data"]["itemType"] == "note"
    assert note["data"]["parentItem"] == "PAPER001"
    assert "accepted" in note["data"]["note"]
    assert note["data"]["tags"] == [{"tag": "sdb"}]
    assert note["data"]["dateAdded"] == "2026-01-01 10:00:00"


def test_attachment_children_carry_web_api_fields(db):
    children = {c["key"]: c["data"] for c in SqliteZoteroGateway(db).get_item_children("PAPER001")}
    assert children["PDF00001"]["itemType"] == "attachment"
    assert children["PDF00001"]["linkMode"] == "imported_file"
    assert children["PDF00001"]["filename"] == "paper.pdf"
    assert children["PDF00001"]["contentType"] == "application/pdf"
    assert children["PDF00001"]["title"] == "Full Text PDF"
    assert children["LINK0001"]["linkMode"] == "linked_file"
    assert children["LINK0001"]["path"] == "/papers/x.pdf"


def test_trashed_children_are_left_out(db):
    keys = [c["key"] for c in SqliteZoteroGateway(db).get_item_children("PAPER002")]
    assert keys == ["NOTE0002"]


def test_sdb_decisions_are_read_offline(db):
    """They were all empty offline: `slr report status` showed 0/0."""
    service = SDBService(SqliteZoteroGateway(db))
    assert [e["decision"] for e in service.inspect_item_sdb("PAPER001")] == ["accepted"]
    assert [e["decision"] for e in service.inspect_item_sdb("PAPER002")] == ["rejected"]


def test_children_of_many_parents_in_one_query(db):
    gateway = SqliteZoteroGateway(db)
    gateway.get_tags()  # open the connection before counting
    statements: list[str] = []
    gateway._get_connection().set_trace_callback(statements.append)
    try:
        by_parent = gateway.get_children_by_parent(["PAPER001", "PAPER002", "NOPE"])
    finally:
        gateway._get_connection().set_trace_callback(None)

    assert sorted(by_parent) == ["PAPER001", "PAPER002"]
    assert len(by_parent["PAPER001"]) == 3
    assert len([s for s in statements if s.lstrip().upper().startswith("SELECT")]) == 2
    assert gateway.get_item_children("NOPE") == []
