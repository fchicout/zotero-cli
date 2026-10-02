"""Tag and collection lookups keep an item-driven plan when zotero.sqlite
has statistics (Issue #424).

After `ANALYZE` (run by users or tools such as DB Browser for SQLite), the
old `IN (?, ?, ...)` lookups made SQLite scan the whole tags table once per
bound ID: 8-25 s for the tag phase of a 5k library. The filter subquery from
#422 fixed it; this pins the plan against Zotero's real itemTags and
collectionItems definitions.
"""

import random
import sqlite3
from pathlib import Path
from typing import List

import pytest

from tests.unit.infra.test_sqlite_large_libraries import SCHEMA as _SCHEMA
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

# Zotero's own definitions (composite primary keys plus a secondary index).
SCHEMA = (
    _SCHEMA.replace(
        "CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);",
        "CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);",
    )
    .replace(
        "CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);",
        "CREATE TABLE itemTags (itemID INT NOT NULL, tagID INT NOT NULL, "
        "type INT NOT NULL DEFAULT 0, PRIMARY KEY (itemID, tagID));"
        "CREATE INDEX itemTags_tagID ON itemTags(tagID);",
    )
    .replace("CREATE INDEX itemTags_item ON itemTags(itemID);", "")
    .replace(
        "CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);",
        "CREATE TABLE collectionItems (collectionID INT NOT NULL, itemID INT NOT NULL, "
        "orderIndex INT NOT NULL DEFAULT 0, PRIMARY KEY (collectionID, itemID));",
    )
    .replace(
        "CREATE INDEX collectionItems_item ON collectionItems(itemID);",
        "CREATE INDEX collectionItems_itemID ON collectionItems(itemID);",
    )
)
PAPERS = 2000
TAGS = 500


@pytest.fixture
def analyzed_db(tmp_path: Path) -> str:
    path = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO tags VALUES (?, ?)", [(t, f"tag{t}") for t in range(2, TAGS + 2)]
    )
    rnd = random.Random(424)
    for paper in range(1, PAPERS + 1):
        conn.execute(
            "INSERT INTO items (itemID, key, version, libraryID, itemTypeID) VALUES (?, ?, 1, 1, 1)",
            (paper, f"P{paper:07d}"),
        )
        conn.execute("INSERT INTO collectionItems (collectionID, itemID) VALUES (1, ?)", (paper,))
        conn.executemany(
            "INSERT INTO itemTags (itemID, tagID) VALUES (?, ?)",
            [(paper, t) for t in rnd.sample(range(2, TAGS + 2), 4)],
        )
    conn.execute("ANALYZE")
    conn.commit()
    conn.close()
    return str(path)


def _plans(gateway: SqliteZoteroGateway, marker: str) -> List[str]:
    """The query plan of each statement the gateway ran whose SQL contains
    `marker`."""
    conn = gateway._get_connection()
    statements: List[str] = []
    conn.set_trace_callback(statements.append)
    try:
        items = list(gateway.get_all_items())
    finally:
        conn.set_trace_callback(None)
    assert len(items) == PAPERS
    matching = [s for s in statements if marker in s]
    assert matching, f"no statement mentions {marker}"
    return [
        " | ".join(row[3] for row in conn.execute(f"EXPLAIN QUERY PLAN {sql}"))  # nosec B608
        for sql in matching
    ]


def test_tag_lookup_is_driven_by_the_items_with_statistics(analyzed_db):
    for plan in _plans(SqliteZoteroGateway(analyzed_db), "FROM itemTags"):
        assert "SCAN t" not in plan, plan
        assert "itemID=?" in plan, plan


def test_collection_lookup_uses_the_index_with_statistics(analyzed_db):
    # With statistics SQLite may walk the (few) collections and probe
    # collectionItems by (collectionID, itemID): fine, 0.33 s for 20k items
    # in 400 collections. What must not happen is a scan of collectionItems.
    for plan in _plans(SqliteZoteroGateway(analyzed_db), "FROM collectionItems ci"):
        assert "SCAN ci" not in plan, plan
        assert "SEARCH ci" in plan, plan
        assert "itemID=?" in plan, plan
