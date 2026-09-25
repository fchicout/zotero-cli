import atexit
import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
from typing import Any, Dict, Iterator, List, Optional, Tuple

from zotero_cli.core.interfaces import JobRepository, ZoteroGateway
from zotero_cli.core.models import Job, ResearchPaper, ZoteroQuery
from zotero_cli.core.utils.collection_resolver import resolve_collection_key
from zotero_cli.core.utils.normalization import normalize_doi
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


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
        self._temp_dir: Optional[str] = None
        if not database_path or not os.path.exists(database_path):
            raise ConfigurationError(f"Zotero database not found at: {database_path}")
        self.original_db_path = database_path

        # Issue #291: unlike online mode (which always scopes every request
        # to the configured library_id/user_id), every query here runs
        # against the entire local zotero.sqlite with no libraryID filter -
        # anyone syncing more than one library locally (a standard Zotero
        # Desktop setup: personal + one or more groups) will silently see
        # items from every synced library, and a Zotero item key collision
        # across libraries can return the wrong item. Warn loudly rather
        # than let this be a silent wrong answer.
        warning = (
            "Warning: --offline mode operates across the ENTIRE local "
            "zotero.sqlite database, not just the configured library_id - "
            "if more than one library (personal + any groups) is synced "
            "locally, results will include items from all of them."
        )
        print(warning, file=sys.stderr)
        logger.warning(warning)

    def _get_connection(self) -> sqlite3.Connection:
        # Create shadow copy
        if not self._temp_db_path:
            # Non-predictable temp path (Issue #240) - a manually joined
            # tempfile.gettempdir()/f"zotero_cli_shadow_{os.getpid()}.sqlite"
            # path is deterministic (PID space is bounded/reused), letting
            # a local attacker on a shared host pre-plant a symlink there.
            # The copy is the user's whole Zotero database, so it lives in a
            # mkdtemp() directory (0700) as a file created 0600 - copying
            # the source's mode (shutil.copy2) left it world-readable - and
            # is removed at exit, not only when the gateway is collected.
            temp_dir = tempfile.mkdtemp(prefix="zotero_cli_shadow_")
            temp_path = os.path.join(temp_dir, "zotero.sqlite")
            fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as dst, open(self.original_db_path, "rb") as src:
                shutil.copyfileobj(src, dst)
            atexit.register(shutil.rmtree, temp_dir, True)
            self._temp_dir = temp_dir
            self._temp_db_path = temp_path

        conn = sqlite3.connect(self._temp_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def __del__(self) -> None:
        temp_dir = getattr(self, "_temp_dir", None)
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

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
        # Venue fields only exist for some item types - like the Web API,
        # include each one only when the item actually has it (Issue #323).
        for venue_field in ("publicationTitle", "proceedingsTitle", "conferenceName", "bookTitle"):
            if row_dict.get(venue_field):
                raw_item["data"][venue_field] = row_dict[venue_field]
        return ZoteroItem.from_raw_zotero_item(raw_item)

    # --- Read Operations ---

    # A top-level item is one that isn't a child row in either
    # itemAttachments or itemNotes (real Zotero has no items.parentItemID
    # column -- parent linkage lives on those two child-specific tables).
    _TOP_LEVEL_ONLY_SQL = """ AND i.itemID NOT IN (
        SELECT itemID FROM itemAttachments WHERE parentItemID IS NOT NULL
        UNION
        SELECT itemID FROM itemNotes WHERE parentItemID IS NOT NULL
    )"""

    # Real Zotero schema has no `collectionData` table and no `parentCollection`
    # string column: `collections` carries `collectionName` directly, and its
    # parent is `parentCollectionID`, an integer FK to another row's
    # `collectionID` -- not a key string. Resolve it to the parent's key via a
    # self-join so the external contract (data.parentCollection = key string,
    # matching ZoteroAPIClient's shape) stays unchanged for callers.
    _COLLECTION_SELECT = """
        SELECT c.key, c.collectionName AS name,
               (SELECT p.key FROM collections p WHERE p.collectionID = c.parentCollectionID)
                   AS parentCollection,
               (SELECT COUNT(*) FROM collectionItems ci
                WHERE ci.collectionID = c.collectionID
                  AND ci.itemID NOT IN (SELECT itemID FROM deletedItems)) AS numItems
        FROM collections c
    """

    def get_all_collections(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(self._COLLECTION_SELECT)
            return [
                {
                    "key": r["key"],
                    "data": {"name": r["name"], "parentCollection": r["parentCollection"]},
                    "meta": {"numItems": r["numItems"]},
                }
                for r in cursor
            ]
        finally:
            conn.close()

    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            row = conn.execute(
                self._COLLECTION_SELECT + " WHERE c.key = ?",
                (collection_key,),
            ).fetchone()
            if row:
                return {
                    "key": row["key"],
                    "data": {"name": row["name"], "parentCollection": row["parentCollection"]},
                    "meta": {"numItems": row["numItems"]},
                }
            return None
        finally:
            conn.close()

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        """Resolves a collection key or name to one key (None if no match).
        Raises AmbiguousCollectionError when a name matches several
        collections, instead of silently taking the first (Issue #381)."""
        return resolve_collection_key(self.get_all_collections(), name)

    def _fetch_items_with_filter(
        self, filter_sql: str = "", params: tuple = (), trash_only: bool = False
    ) -> Iterator[ZoteroItem]:
        conn = self._get_connection()
        try:
            membership = "IN" if trash_only else "NOT IN"
            # Zotero 7 stores every PDF highlight/note as an `items` row whose
            # parent is in itemAnnotations; they aren't library items and
            # usually outnumber the references (Issue #423).
            where_template = """
                WHERE i.itemID {membership} (SELECT itemID FROM deletedItems)
                  AND it.typeName <> 'annotation'
                  {filter_sql}
            """
            # filter_sql/membership are always fixed literal fragments supplied by call
            # sites in this file (never user input); actual values are passed via the
            # parameterized `params` tuple, not interpolated into the SQL text.
            where_sql = where_template.format(filter_sql=filter_sql, membership=membership)
            # The creators/collections/tags lookups below select by this same
            # filter instead of binding one "?" per matched item: SQLite caps
            # bound variables at 32,766 in most builds (Issue #422).
            matched_ids_sql = (
                "SELECT i.itemID FROM items i "
                "JOIN itemTypes it ON i.itemTypeID = it.itemTypeID" + where_sql  # nosec B608
            )
            query_sql_template = """
                SELECT i.itemID, i.key, i.version, i.libraryID, it.typeName,
                       (SELECT k.key FROM items k WHERE k.itemID = COALESCE(
                           (SELECT parentItemID FROM itemAttachments WHERE itemID = i.itemID),
                           (SELECT parentItemID FROM itemNotes WHERE itemID = i.itemID)
                       )) as parentKey,
                       MAX(CASE WHEN f.fieldName = 'title' THEN dv.value END) as title,
                       MAX(CASE WHEN f.fieldName = 'abstractNote' THEN dv.value END) as abstractNote,
                       MAX(CASE WHEN f.fieldName = 'date' THEN dv.value END) as date,
                       MAX(CASE WHEN f.fieldName = 'DOI' THEN dv.value END) as DOI,
                       MAX(CASE WHEN f.fieldName = 'url' THEN dv.value END) as url,
                       MAX(CASE WHEN f.fieldName = 'extra' THEN dv.value END) as extra,
                       MAX(CASE WHEN f.fieldName = 'publicationTitle' THEN dv.value END)
                           as publicationTitle,
                       MAX(CASE WHEN f.fieldName = 'proceedingsTitle' THEN dv.value END)
                           as proceedingsTitle,
                       MAX(CASE WHEN f.fieldName = 'conferenceName' THEN dv.value END)
                           as conferenceName,
                       MAX(CASE WHEN f.fieldName = 'bookTitle' THEN dv.value END) as bookTitle
                FROM items i
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                LEFT JOIN itemData id ON i.itemID = id.itemID
                LEFT JOIN fields f ON id.fieldID = f.fieldID
                LEFT JOIN itemDataValues dv ON id.valueID = dv.valueID
                {where_sql}
                GROUP BY i.itemID
            """
            query_sql = query_sql_template.format(where_sql=where_sql)  # nosec B608
            rows = conn.execute(query_sql, params).fetchall()
            if not rows:
                return

            creators_by_item: Dict[int, List[Dict[str, Any]]] = {}
            creator_cursor = conn.execute(
                f"""
                SELECT ic.itemID, c.firstName, c.lastName, ct.creatorType
                FROM itemCreators ic
                JOIN creators c ON ic.creatorID = c.creatorID
                JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
                WHERE ic.itemID IN ({matched_ids_sql})
                ORDER BY ic.itemID, ic.orderIndex
            """,  # nosec B608
                params,
            )
            for r in creator_cursor:
                creators_by_item.setdefault(r["itemID"], []).append(
                    {
                        "creatorType": r["creatorType"],
                        "firstName": r["firstName"],
                        "lastName": r["lastName"],
                    }
                )

            collections_by_item: Dict[int, List[str]] = {}
            col_cursor = conn.execute(
                f"""
                SELECT ci.itemID, c.key
                FROM collectionItems ci
                JOIN collections c ON ci.collectionID = c.collectionID
                WHERE ci.itemID IN ({matched_ids_sql})
            """,  # nosec B608
                params,
            )
            for r in col_cursor:
                collections_by_item.setdefault(r["itemID"], []).append(r["key"])

            tags_by_item: Dict[int, List[str]] = {}
            tag_cursor = conn.execute(
                f"""
                SELECT itg.itemID, t.name
                FROM itemTags itg
                JOIN tags t ON itg.tagID = t.tagID
                WHERE itg.itemID IN ({matched_ids_sql})
            """,  # nosec B608
                params,
            )
            for r in tag_cursor:
                tags_by_item.setdefault(r["itemID"], []).append(r["name"])

            for row in rows:
                yield self._map_row_to_item(
                    row,
                    creators_by_item.get(row["itemID"], []),
                    collections_by_item.get(row["itemID"], []),
                    tags_by_item.get(row["itemID"], []),
                )
        finally:
            conn.close()

    # Quick-search subqueries; each takes one LIKE pattern per placeholder.
    _MATCH_FIELDS_SQL = """i.itemID IN (
            SELECT sd.itemID FROM itemData sd
            JOIN fields sf ON sd.fieldID = sf.fieldID
            JOIN itemDataValues sv ON sd.valueID = sv.valueID
            WHERE {field_filter} sv.value LIKE ? ESCAPE '\\')"""
    _MATCH_CREATORS_SQL = """i.itemID IN (
            SELECT sic.itemID FROM itemCreators sic
            JOIN creators sc ON sic.creatorID = sc.creatorID
            WHERE sc.lastName LIKE ? ESCAPE '\\' OR sc.firstName LIKE ? ESCAPE '\\')"""
    _MATCH_NOTE_TITLE_SQL = (
        "i.itemID IN (SELECT itemID FROM itemNotes WHERE title LIKE ? ESCAPE '\\')"
    )
    _MATCH_NOTE_TEXT_SQL = (
        "i.itemID IN (SELECT itemID FROM itemNotes WHERE note LIKE ? ESCAPE '\\')"
    )

    @staticmethod
    def _like_pattern(word: str) -> str:
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    @staticmethod
    def _split_alternatives(value: str) -> Tuple[bool, List[str]]:
        """Web API filter syntax: `a || b` matches either, `-a` excludes."""
        negate = value.startswith("-")
        if negate:
            value = value[1:]
        return negate, [v.strip() for v in value.split("||") if v.strip()]

    def _search_filter(self, query: ZoteroQuery) -> Tuple[str, List[Any]]:
        """
        Translates a ZoteroQuery into SQL with the Web API's semantics
        (Issue #366: the query used to be ignored, so every offline search
        returned the whole library, notes and attachments included):

        - `q`: every whitespace-separated word must match (case-insensitive
          substring). `titleCreatorYear` looks at the title, date, creator
          names and note titles; `everything` at any field and note text.
        - `item_type` and `tag`: exact values, `a || b` and `-a`.
        - `since`: items whose version is newer than the given one.
        """
        clauses: List[str] = []
        params: List[Any] = []

        if query.q:
            everything = query.qmode == "everything"
            field_filter = "" if everything else "sf.fieldName IN ('title', 'date') AND"
            fields_sql = self._MATCH_FIELDS_SQL.format(field_filter=field_filter)
            note_sql = self._MATCH_NOTE_TEXT_SQL if everything else self._MATCH_NOTE_TITLE_SQL
            for word in query.q.split():
                pattern = self._like_pattern(word)
                clauses.append(
                    f"({fields_sql} OR {self._MATCH_CREATORS_SQL} OR {note_sql})"
                )
                params.extend([pattern, pattern, pattern, pattern])

        if query.item_type:
            negate, types = self._split_alternatives(query.item_type)
            if types:
                placeholders = ",".join("?" for _ in types)
                clauses.append(f"it.typeName {'NOT IN' if negate else 'IN'} ({placeholders})")
                params.extend(types)

        if query.tag:
            negate, tags = self._split_alternatives(query.tag)
            if tags:
                placeholders = ",".join("?" for _ in tags)
                # Only fixed keywords and "?" placeholders are interpolated;
                # the tag names are bound as parameters.
                clauses.append(
                    f"i.itemID {'NOT IN' if negate else 'IN'} ("
                    "SELECT stg.itemID FROM itemTags stg JOIN tags st ON stg.tagID = st.tagID "
                    f"WHERE st.name IN ({placeholders}))"  # nosec B608
                )
                params.extend(tags)

        if query.since:
            clauses.append("i.version > ?")
            params.append(query.since)

        return "".join(f" AND {c}" for c in clauses), params

    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        filter_sql, params = self._search_filter(query)
        return self._fetch_items_with_filter(filter_sql, tuple(params))

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
            filter_sql += self._TOP_LEVEL_ONLY_SQL
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
        # No items.parentItemID in the real schema -- child linkage lives on
        # itemAttachments/itemNotes instead (see _TOP_LEVEL_ONLY_SQL above).
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT key FROM items
                WHERE itemID IN (
                    SELECT itemID FROM itemAttachments
                    WHERE parentItemID = (SELECT itemID FROM items WHERE key = ?)
                    UNION
                    SELECT itemID FROM itemNotes
                    WHERE parentItemID = (SELECT itemID FROM items WHERE key = ?)
                )
            """,
                (item_key, item_key),
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
        """
        An exact SQL match on the stored DOI value would miss bare/URL-
        form/case differences between the queried DOI and how it's
        actually stored (Issue #252) - the same structural gap #205/#221
        fixed for the online ZoteroAPIClient by abandoning an indexed
        search in favor of a client-side scan with normalize_doi() on
        both sides. Mirror that here rather than trusting an exact SQL
        string match.
        """
        target = normalize_doi(doi)
        if not target:
            return
        for item in self.get_all_items():
            if item.doi and normalize_doi(item.doi) == target:
                yield item

    def get_all_items(self) -> Iterator[ZoteroItem]:
        return self._fetch_items_with_filter()

    def get_orphan_items(self, top_only: bool = False) -> Iterator[ZoteroItem]:
        filter_sql = "AND i.itemID NOT IN (SELECT itemID FROM collectionItems)"
        if top_only:
            filter_sql += self._TOP_LEVEL_ONLY_SQL
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
        # Deliberate, not incidental (Issue #150): once a web backend is
        # polling/draining this queue alongside CLI invocations, WAL lets
        # readers (status polls) proceed without blocking on an in-flight
        # writer (a worker popping/completing a job), instead of the default
        # rollback-journal mode's single-writer-blocks-everyone behavior.
        conn.execute("PRAGMA journal_mode=WAL")
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
                    last_error TEXT,
                    library_id TEXT
                )
            """
                )
                existing_columns = {
                    row["name"] for row in conn.execute("PRAGMA table_info(jobs)")
                }
                if "library_id" not in existing_columns:
                    conn.execute("ALTER TABLE jobs ADD COLUMN library_id TEXT")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_task_status "
                    "ON jobs (task_type, status)"
                )
        finally:
            conn.close()

    def enqueue(self, job: Job) -> int:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                INSERT INTO jobs (item_key, task_type, status, attempts, next_retry_at, payload, last_error, library_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                    (
                        job.item_key,
                        job.task_type,
                        job.status,
                        job.attempts,
                        job.next_retry_at,
                        json.dumps(job.payload),
                        job.last_error,
                        job.library_id,
                    ),
                )
                if cursor.lastrowid is None:
                    raise sqlite3.Error("Failed to retrieve last inserted job ID")
                return int(cursor.lastrowid)
        finally:
            conn.close()

    def get_next_pending(self, task_type: str, library_id: Optional[str] = None) -> Optional[Job]:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                query = """
                    SELECT * FROM jobs
                    WHERE task_type = ? AND status IN ('PENDING', 'RETRY')
                    AND (next_retry_at IS NULL OR next_retry_at <= datetime('now'))
                """
                params: List[str] = [task_type]
                if library_id is not None:
                    # NULL library_id = a legacy/unscoped job (enqueued before
                    # scoping existed, or by a caller with no library_id) -
                    # visible to every queue rather than orphaned by the
                    # filter below.
                    query += " AND (library_id = ? OR library_id IS NULL)"
                    params.append(library_id)
                query += " ORDER BY id ASC LIMIT 1"
                row = conn.execute(query, params).fetchone()

                if row:
                    # A legacy (library_id IS NULL) job claimed by a scoped
                    # queue is stamped with that library_id in the same
                    # BEGIN IMMEDIATE transaction (Issue #289) - otherwise
                    # it stays poachable by every other library's queue on
                    # every subsequent retry cycle, not just this claim,
                    # risking cross-tenant job execution against the wrong
                    # library's gateway.
                    if library_id is not None and row["library_id"] is None:
                        conn.execute(
                            "UPDATE jobs SET status = 'PROCESSING', library_id = ? "
                            "WHERE id = ? AND library_id IS NULL",
                            (library_id, row["id"]),
                        )
                    else:
                        conn.execute(
                            "UPDATE jobs SET status = 'PROCESSING' WHERE id = ?", (row["id"],)
                        )
                    job = self._map_row_to_job(row)
                    job.status = "PROCESSING"
                    if library_id is not None and row["library_id"] is None:
                        job.library_id = library_id
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

    def list_jobs(
        self, task_type: Optional[str] = None, library_id: Optional[str] = None, limit: int = 100
    ) -> List[Job]:
        conn = self._get_connection()
        try:
            query = "SELECT * FROM jobs"
            conditions = []
            params: List[Any] = []
            if task_type:
                conditions.append("task_type = ?")
                params.append(task_type)
            if library_id is not None:
                # See get_next_pending: NULL library_id is a legacy/unscoped
                # job, shown regardless of which library is asking.
                conditions.append("(library_id = ? OR library_id IS NULL)")
                params.append(library_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            cursor = conn.execute(query, params)
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
            library_id=row["library_id"],
        )
