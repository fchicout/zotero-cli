"""
Builds a small offline library the release smoke test runs the built binary
against (Issue #399): a `zotero.sqlite` with one collection, one paper with
an attached PDF, and one paper without one, using the real Zotero schema
(the same subset `tests/unit/test_sqlite_repo.py` uses).

    python scripts/build_smoke_fixture.py <output_dir>

Writes <output_dir>/zotero.sqlite and <output_dir>/sample.pdf.
"""

import sqlite3
import sys
from pathlib import Path

# The one-page PDF `core/services/selftest.py` already embeds for the same
# purpose (checking PDF text extraction actually works in the binary) - kept
# in one place rather than duplicated.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from zotero_cli.core.services.selftest import SAMPLE_PDF, SAMPLE_PDF_TEXT  # noqa: E402

SCHEMA = """
CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER,
    itemTypeID INTEGER, dateAdded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dateModified TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, linkMode INTEGER,
    contentType TEXT, path TEXT);
CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, note TEXT, title TEXT);
CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT, fieldMode INTEGER);
CREATE TABLE creatorTypes (creatorTypeID INTEGER PRIMARY KEY, creatorType TEXT);
CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER);
CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, key TEXT, collectionName TEXT,
    parentCollectionID INTEGER);
CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);

INSERT INTO itemTypes VALUES (1, 'journalArticle'), (2, 'attachment'), (3, 'note');
INSERT INTO fields VALUES (1, 'title'), (2, 'date'), (3, 'DOI');
INSERT INTO creatorTypes VALUES (1, 'author');
INSERT INTO creators VALUES (1, 'Ada', 'Lovelace', 0);

INSERT INTO items VALUES (1, 'SMOKE001', 1, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO itemDataValues VALUES (1, 'A Paper With a PDF'), (2, '2024'), (3, '10.1/smoke');
INSERT INTO itemData VALUES (1, 1, 1), (1, 2, 2), (1, 3, 3);
INSERT INTO itemCreators VALUES (1, 1, 1, 0);

INSERT INTO items VALUES (2, 'SMOKE002', 1, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO itemDataValues VALUES (4, 'A Paper Without a PDF');
INSERT INTO itemData VALUES (2, 1, 4);

INSERT INTO items VALUES (3, 'SMOKEPDF', 1, 1, 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO itemAttachments VALUES (3, 1, 0, 'application/pdf', 'storage:sample.pdf');

INSERT INTO collections VALUES (1, 'SMOKECOL', 'Smoke Test', NULL);
INSERT INTO collectionItems VALUES (1, 1), (1, 2);
"""


def build(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "zotero.sqlite"
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    (output_dir / "sample.pdf").write_bytes(SAMPLE_PDF)
    print(f"Wrote {db_path} and {output_dir / 'sample.pdf'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <output_dir>")
    build(Path(sys.argv[1]))
    # sanity: importable and non-empty, for callers that only check exit code
    assert SAMPLE_PDF_TEXT
