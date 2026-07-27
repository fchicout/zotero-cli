import json
import os
import shutil
import sqlite3
import tempfile
from typing import Any, Dict, Iterator, List, Optional

from zotero_cli.core.interfaces import JobRepository, ZoteroGateway
from zotero_cli.core.models import Job, ResearchPaper, ZoteroQuery
from zotero_cli.core.zotero_item import ZoteroItem


class ConfigurationError(Exception):
    """Raised when an operation is not permitted in the current configuration."""

    pass


OFFLINE_READ_ONLY = "Offline mode is read-only"


class SqliteZoteroGateway(ZoteroGateway):
    """
    Read-only implementation of ZoteroGateway using local zotero.sqlite.
    Uses a 'Shadow Copy' strategy to avoid locking the database.
    """

    def __init__(self, database_path: str):
        self._temp_db_path: Optional[str] = None
        if not database_path or not os.path.exists(database_path):
            raise ConfigurationError(f"Zotero database not found at: {database_path}")
        self.original_db_path = database_path

    def _get_connection(self) -> sqlite3.Connection:
        # Create shadow copy
        if not self._temp_db_path:
            temp_dir = tempfile.gettempdir()
            self._temp_db_path = os.path.join(temp_dir, f"zotero_cli_shadow_{os.getpid()}.sqlite")
            shutil.copy2(self.original_db_path, self._temp_db_path)

        conn = sqlite3.connect(self._temp_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def __del__(self) -> None:
        if self._temp_db_path and os.path.exists(self._temp_db_path):
            try:
                os.remove(self._temp_db_path)
            except OSError:
                pass

    def _map_row_to_item(
        self,
        row: sqlite3.Row,
        creators: List[Dict[str, Any]],
        collections: List[str],
        tags: List[str],
    ) -> ZoteroItem:
        row_dict = dict(row)
        raw_item = {
            "key": row_dict["key"],
            "version": row_dict["version"],
            "libraryID": row_dict["libraryID"],
            "data": {
                "key": row_dict["key"],
                "version": row_dict["version"],
                "itemType": row_dict["typeName"],
                "parentItem": row_dict.get("parentKey"),
                "title": row_dict.get("title") or "",
                "abstractNote": row_dict.get("abstractNote") or "",
                "date": row_dict.get("date") or "",
                "DOI": row_dict.get("DOI") or "",
                "url": row_dict.get("url") or "",
                "extra": row_dict.get("extra") or "",
                "creators": creators,
                "collections": collections,
                "tags": [{"tag": t} for t in tags],
            },
        }
        return ZoteroItem.from_raw_zotero_item(raw_item)

    # --- Read Operations ---

    def get_all_collections(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT c.key, c.parentCollection, cd.name
                FROM collections c
                JOIN collectionData cd ON c.collectionID = cd.collectionID
            """
            )
            return [
                {
                    "key": r["key"],
                    "data": {"name": r["name"], "parentCollection": r["parentCollection"]},
                }
                for r in cursor
            ]
        finally:
            conn.close()

    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT c.key, c.parentCollection, cd.name
                FROM collections c
                JOIN collectionData cd ON c.collectionID = cd.collectionID
                WHERE c.key = ?
            """,
                (collection_key,),
            ).fetchone()
            if row:
                return {
                    "key": row["key"],
                    "data": {"name": row["name"], "parentCollection": row["parentCollection"]},
                }
            return None
        finally:
            conn.close()

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        cols = self.get_all_collections()
        for c in cols:
            if c.get("data", {}).get("name") == name:
                return str(c["key"])
        return None

    def _fetch_items_with_filter(
        self, filter_sql: str = "", params: tuple = (), trash_only: bool = False
    ) -> Iterator[ZoteroItem]:
        conn = self._get_connection()
        try:
            membership = "IN" if trash_only else "NOT IN"
            query_sql_template = """
                SELECT i.key, i.version, i.libraryID, it.typeName,
                       (SELECT key FROM items WHERE itemID = i.parentItemID) as parentKey,
                       MAX(CASE WHEN f.fieldName = 'title' THEN dv.value END) as title,
                       MAX(CASE WHEN f.fieldName = 'abstractNote' THEN dv.value END) as abstractNote,
                       MAX(CASE WHEN f.fieldName = 'date' THEN dv.value END) as date,
                       MAX(CASE WHEN f.fieldName = 'DOI' THEN dv.value END) as DOI,
                       MAX(CASE WHEN f.fieldName = 'url' THEN dv.value END) as url,
                       MAX(CASE WHEN f.fieldName = 'extra' THEN dv.value END) as extra
                FROM items i
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                LEFT JOIN itemData id ON i.itemID = id.itemID
                LEFT JOIN fields f ON id.fieldID = f.fieldID
                LEFT JOIN itemDataValues dv ON id.valueID = dv.valueID
                WHERE i.itemID {membership} (SELECT itemID FROM deletedItems)
                  {filter_sql}
                GROUP BY i.itemID
            """
            # filter_sql/membership are always fixed literal fragments supplied by call
            # sites in this file (never user input); actual values are passed via the
            # parameterized `params` tuple below, not interpolated into the SQL text.
            query_sql = query_sql_template.format(
                filter_sql=filter_sql, membership=membership
            )  # nosec B608
            cursor = conn.execute(query_sql, params)
            for row in cursor:
                creator_cursor = conn.execute(
                    """
                    SELECT cd.firstName, cd.lastName, ct.creatorType
                    FROM itemCreators ic
                    JOIN creators c ON ic.creatorID = c.creatorID
                    JOIN creatorData cd ON c.creatorDataID = cd.creatorDataID
                    JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
                    WHERE ic.itemID = (SELECT itemID FROM items WHERE key = ?)
                    ORDER BY ic.orderIndex
                """,
                    (row["key"],),
                )
                creators = [
                    {
                        "creatorType": r["creatorType"],
                        "firstName": r["firstName"],
                        "lastName": r["lastName"],
                    }
                    for r in creator_cursor
                ]

                col_cursor = conn.execute(
                    """
                    SELECT c.key
                    FROM collectionItems ci
                    JOIN collections c ON ci.collectionID = c.collectionID
                    WHERE ci.itemID = (SELECT itemID FROM items WHERE key = ?)
                """,
                    (row["key"],),
                )
                collections = [r["key"] for r in col_cursor]

                tag_cursor = conn.execute(
                    """
                    SELECT t.name
                    FROM itemTags it
                    JOIN tags t ON it.tagID = t.tagID
                    WHERE it.itemID = (SELECT itemID FROM items WHERE key = ?)
                """,
                    (row["key"],),
                )
                tags = [r["name"] for r in tag_cursor]

                yield self._map_row_to_item(row, creators, collections, tags)
        finally:
            conn.close()

    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        return self._fetch_items_with_filter()

    def get_items_in_collection(
        self, collection_id: str, top_only: bool = False
    ) -> Iterator[ZoteroItem]:
        filter_sql = """
            AND i.itemID IN (
                SELECT ci.itemID
                FROM collectionItems ci
                JOIN collections c ON ci.collectionID = c.collectionID
                WHERE c.key = ?
            )
        """
        if top_only:
            filter_sql += " AND i.parentItemID IS NULL"
        return self._fetch_items_with_filter(filter_sql, (collection_id,))

    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        items = list(self._fetch_items_with_filter("AND i.key = ?", (item_key,)))
        return items[0] if items else None

    def get_tags(self) -> List[str]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT name FROM tags")
            return [r["name"] for r in cursor]
        finally:
            conn.close()

    def get_tags_for_item(self, item_key: str) -> List[str]:
        item = self.get_item(item_key)
        return item.tags if item else []

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT key FROM items
                WHERE parentItemID = (SELECT itemID FROM items WHERE key = ?)
            """,
                (item_key,),
            )
            return [{"key": r["key"]} for r in cursor]
        finally:
            conn.close()

    # --- Write Operations (FORBIDDEN in Offline mode) ---

    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def get_item_template(self, item_type: str) -> Dict[str, Any]:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def update_items(self, items_data: List[Dict[str, Any]]) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def delete_item(self, item_key: str, version: int) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def delete_collection(self, collection_key: str, version: int) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def rename_collection(self, collection_key: str, version: int, name: str) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def add_tags(self, item_key: str, tags: List[str]) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def delete_tags(self, tags: List[str], version: int) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def update_note(
        self, note_key: str, version: int, note_content: str, parent_item_key: Optional[str] = None
    ) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def upload_attachment(
        self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf"
    ) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def download_attachment(self, item_key: str, save_path: str) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def update_attachment_link(self, item_key: str, version: int, new_path: str) -> bool:
        raise ConfigurationError(OFFLINE_READ_ONLY)

    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        filter_sql = """
            AND i.itemID IN (
                SELECT itg.itemID
                FROM itemTags itg
                JOIN tags t ON itg.tagID = t.tagID
                WHERE t.name = ?
            )
        """
        return self._fetch_items_with_filter(filter_sql, (tag,))

    def get_items_by_doi(self, doi: str) -> Iterator[ZoteroItem]:
        filter_sql = """
            AND i.itemID IN (
                SELECT id.itemID
                FROM itemData id
                JOIN fields f ON id.fieldID = f.fieldID
                JOIN itemDataValues dv ON id.valueID = dv.valueID
                WHERE f.fieldName = 'DOI' AND dv.value = ?
            )
        """
        return self._fetch_items_with_filter(filter_sql, (doi,))

    def get_all_items(self) -> Iterator[ZoteroItem]:
        return self._fetch_items_with_filter()

    def get_orphan_items(self, top_only: bool = False) -> Iterator[ZoteroItem]:
        filter_sql = "AND i.itemID NOT IN (SELECT itemID FROM collectionItems)"
        if top_only:
            filter_sql += " AND i.parentItemID IS NULL"
        return self._fetch_items_with_filter(filter_sql)

    def get_trash_items(self) -> Iterator[ZoteroItem]:
        return self._fetch_items_with_filter(trash_only=True)

    # --- Narrow Write Exception: item trash/restore (Issue #145) ---
    #
    # Every other write in this class is forbidden (see OFFLINE_READ_ONLY
    # below) because _get_connection()'s shadow-copy strategy makes writes
    # pointless there -- they'd land on a throwaway temp file, not the real
    # database. trash_item/restore_item are the sole exception: they open
    # original_db_path directly and replicate, statement-for-statement, what
    # Zotero Desktop's own Zotero.Items.trash()/trashTx() and
    # `item.deleted = false; item.save()` write to zotero.sqlite (confirmed
    # against Zotero's client source), so a CLI-initiated trash/restore is
    # indistinguishable from one done in Desktop and safely picked up by
    # Desktop's next real sync (synced=0 marks the row dirty; version is
    # deliberately left untouched -- only the server bumps that on sync).

    def _get_write_connection(self, timeout: float = 5.0) -> sqlite3.Connection:
        """
        Opens a direct connection to the real zotero.sqlite -- deliberately
        NOT _get_connection()'s shadow copy, which is deleted on __del__ and
        would silently discard any write made through it. `timeout` sets
        SQLite's busy-retry window so a momentary lock (e.g. Desktop mid-write)
        is retried rather than failing immediately.
        """
        conn = sqlite3.connect(self.original_db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row
        return conn

    def trash_item(self, item_key: str) -> bool:
        """
        Moves an item to the trash, matching Desktop's Zotero.Items.trash():
        bumps dateModified/clientDateModified, marks the row dirty (synced=0)
        so Desktop's next sync pushes the deletion to the server, and adds a
        deletedItems row. Idempotent (INSERT OR IGNORE), same as Desktop's own
        query. Returns False if no item with this key exists.
        """
        conn = self._get_write_connection()
        try:
            row = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchone()
            if not row:
                return False
            item_id = row["itemID"]
            conn.execute(
                "UPDATE items SET synced=0, clientDateModified=CURRENT_TIMESTAMP, "
                "dateModified=CURRENT_TIMESTAMP WHERE itemID=?",
                (item_id,),
            )
            conn.execute("INSERT OR IGNORE INTO deletedItems (itemID) VALUES (?)", (item_id,))
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            conn.rollback()
            raise RuntimeError(
                f"Could not write to zotero.sqlite ({e}). If Zotero Desktop is open and "
                "busy, wait a moment and retry, or close it first."
            ) from e
        finally:
            conn.close()

    def restore_item(self, item_key: str) -> bool:
        """
        Reverses trash_item(), matching Desktop's `item.deleted = false;
        item.save()` path: bumps dateModified/clientDateModified, marks the
        row dirty (synced=0), and removes the deletedItems row. Does NOT
        replicate Desktop's merge-relations cleanup (stripping dc:replaces
        relations left by a prior `item merge` on this item) -- narrow edge
        case, deliberately left untouched rather than guessing at the
        Relations table's bookkeeping. Returns False if no item with this
        key exists.
        """
        conn = self._get_write_connection()
        try:
            row = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchone()
            if not row:
                return False
            item_id = row["itemID"]
            conn.execute(
                "UPDATE items SET dateModified=CURRENT_TIMESTAMP, synced=0, "
                "clientDateModified=CURRENT_TIMESTAMP WHERE itemID=?",
                (item_id,),
            )
            conn.execute("DELETE FROM deletedItems WHERE itemID=?", (item_id,))
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            conn.rollback()
            raise RuntimeError(
                f"Could not write to zotero.sqlite ({e}). If Zotero Desktop is open and "
                "busy, wait a moment and retry, or close it first."
            ) from e
        finally:
            conn.close()

    def verify_credentials(self) -> bool:
        return os.path.exists(self.original_db_path)

    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        return []


class SqliteJobRepository(JobRepository):
    """
    Persistent job queue implementation using SQLite.
    """

    def __init__(self, database_path: str):
        self.database_path = database_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                CREATE TABLE IF NOT EXISTS jobs (
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
        finally:
            conn.close()

    def enqueue(self, job: Job) -> int:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                INSERT INTO jobs (item_key, task_type, status, attempts, next_retry_at, payload, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                    (
                        job.item_key,
                        job.task_type,
                        job.status,
                        job.attempts,
                        job.next_retry_at,
                        json.dumps(job.payload),
                        job.last_error,
                    ),
                )
                if cursor.lastrowid is None:
                    raise sqlite3.Error("Failed to retrieve last inserted job ID")
                return int(cursor.lastrowid)
        finally:
            conn.close()

    def get_next_pending(self, task_type: str) -> Optional[Job]:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE task_type = ? AND status IN ('PENDING', 'RETRY')
                    AND (next_retry_at IS NULL OR next_retry_at <= datetime('now'))
                    ORDER BY id ASC LIMIT 1
                """,
                    (task_type,),
                ).fetchone()

                if row:
                    conn.execute("UPDATE jobs SET status = 'PROCESSING' WHERE id = ?", (row["id"],))
                    job = self._map_row_to_job(row)
                    job.status = "PROCESSING"
                    return job
                return None
        finally:
            conn.close()

    def update_job(self, job: Job) -> bool:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                UPDATE jobs
                SET status = ?, attempts = ?, next_retry_at = ?, payload = ?, last_error = ?
                WHERE id = ?
            """,
                    (
                        job.status,
                        job.attempts,
                        job.next_retry_at,
                        json.dumps(job.payload),
                        job.last_error,
                        job.id,
                    ),
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    def get_job(self, job_id: int) -> Optional[Job]:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row:
                return self._map_row_to_job(row)
            return None
        finally:
            conn.close()

    def list_jobs(self, task_type: Optional[str] = None, limit: int = 100) -> List[Job]:
        conn = self._get_connection()
        try:
            if task_type:
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE task_type = ? ORDER BY id DESC LIMIT ?",
                    (task_type, limit),
                )
            else:
                cursor = conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))
            return [self._map_row_to_job(row) for row in cursor]
        finally:
            conn.close()

    def _map_row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            item_key=row["item_key"],
            task_type=row["task_type"],
            status=row["status"],
            attempts=row["attempts"],
            next_retry_at=row["next_retry_at"],
            payload=json.loads(row["payload"]),
            last_error=row["last_error"],
        )
