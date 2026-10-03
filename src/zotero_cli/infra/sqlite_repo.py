import atexit
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import threading
from typing import Any, Dict, Iterator, List, Optional, Tuple

from zotero_cli.core import annotations as annotation_records
from zotero_cli.core.exceptions import ConfigurationError, OfflineReadOnly, UsageError
from zotero_cli.core.interfaces import JobRepository, ZoteroGateway
from zotero_cli.core.models import Job, ResearchPaper, ZoteroQuery
from zotero_cli.core.utils.collection_resolver import resolve_collection_key
from zotero_cli.core.utils.normalization import normalize_doi
from zotero_cli.core.utils.notify import NotifyMixin
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


# One exception hierarchy for the whole CLI (Issue #370): this module used
# to define its own ConfigurationError, which main() never caught.
OFFLINE_READ_ONLY = "Offline mode is read-only"

_unscoped_warning_shown = False


def _warn_unscoped_once() -> None:
    """Once per process (Issue #385): each service builds its own gateway,
    so the warning used to repeat up to 7 times before any output."""
    global _unscoped_warning_shown
    if _unscoped_warning_shown:
        return
    _unscoped_warning_shown = True
    logger.warning(
        "--offline mode operates across the ENTIRE local zotero.sqlite database, not just "
        "the configured library_id - if more than one library (personal + any groups) is "
        "synced locally, results will include items from all of them."
    )


# --- One shadow copy per process (Issue #436) ---
#
# Every service builds its own gateway, and each used to copy the whole
# database (2 x 842 MB for `slr report status`) and open a connection per
# call (12,218 for one export). The copy is now shared by every gateway and
# keyed by the file's identity, so a changed database (after `item trash`)
# is copied again.
_shadow_lock = threading.Lock()
_shadows: Dict[Tuple[str, int, int], str] = {}
# One connection per thread to the current copy, shared by every gateway
# (`serve` runs handlers in a threadpool; a connection stays in its thread).
_thread_state = threading.local()
# (shadow path, connection): lets a stale path's connections be closed
# before its directory is removed (Issue #413: shutil.rmtree silently
# failed on Windows, which can't delete a file a connection still has
# open, leaking the old copy on every database change).
_all_connections: List[Tuple[str, sqlite3.Connection]] = []


def _shadow_parent() -> Optional[str]:
    """A private directory in the user's cache, on disk: /tmp is tmpfs on
    Fedora and Arch, where each copy would sit in RAM. None falls back to
    the system temp directory."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    path = os.path.join(base, "zotero-cli")
    try:
        os.makedirs(path, mode=0o700, exist_ok=True)
        if os.name != "nt":
            os.chmod(path, 0o700)
    except OSError:
        return None
    return path


def _shadow_copy(database_path: str) -> str:
    """The process-wide copy of `database_path`, made on first use."""
    real = os.path.realpath(database_path)
    st = os.stat(real)
    key = (real, st.st_mtime_ns, st.st_size)
    with _shadow_lock:
        cached = _shadows.get(key)
        if cached and os.path.exists(cached):
            return cached
        for old in [k for k in _shadows if k[0] == real]:
            stale_path = _shadows.pop(old)
            _close_connections_for(stale_path)
            shutil.rmtree(os.path.dirname(stale_path), ignore_errors=True)
        # Non-predictable temp path (Issue #240) - a manually joined
        # tempfile.gettempdir()/f"zotero_cli_shadow_{os.getpid()}.sqlite"
        # path is deterministic (PID space is bounded/reused), letting
        # a local attacker on a shared host pre-plant a symlink there.
        # The copy is the user's whole Zotero database, so it lives in a
        # mkdtemp() directory (0700) as a file created 0600 - copying
        # the source's mode (shutil.copy2) left it world-readable - and
        # is removed at exit. A plain file copy, since Zotero Desktop
        # holds an exclusive lock on the live database while it runs.
        temp_dir = tempfile.mkdtemp(prefix="zotero_cli_shadow_", dir=_shadow_parent())
        temp_path = os.path.join(temp_dir, "zotero.sqlite")
        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as dst, open(real, "rb") as src:
            shutil.copyfileobj(src, dst)
        _shadows[key] = temp_path
        return temp_path


def _shadow_connection(database_path: str) -> Tuple[sqlite3.Connection, str]:
    """This thread's connection to the current copy of `database_path`."""
    path = _shadow_copy(database_path)
    conns: Dict[str, Tuple[sqlite3.Connection, str]] = getattr(_thread_state, "conns", {})
    _thread_state.conns = conns
    cached = conns.get(database_path)
    if cached is not None and cached[1] == path:
        return cached
    if cached is not None:
        cached[0].close()  # the database changed and was copied again
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    with _shadow_lock:
        _all_connections.append((path, conn))
    conns[database_path] = (conn, path)
    return conn, path


def _close_connections_for(path: str) -> None:
    """Closes and forgets every open connection to `path` from the calling
    thread (caller holds _shadow_lock). Windows can't delete a file a
    connection still has open. sqlite3 refuses to close a connection from a
    thread other than the one that opened it (silently, via the same
    sqlite3.Error catch every close here already uses) - a connection held
    open by another thread when the database changes can still block the
    old copy's removal there; the file is cleaned up at exit either way."""
    remaining = []
    for entry_path, conn in _all_connections:
        if entry_path == path:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        else:
            remaining.append((entry_path, conn))
    _all_connections[:] = remaining


def _cleanup_shadows() -> None:
    with _shadow_lock:
        for path in _shadows.values():
            _close_connections_for(path)
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)
        _shadows.clear()


atexit.register(_cleanup_shadows)


# How Zotero writes the path of a file it keeps in its own storage folder.
STORAGE_PREFIX = "storage:"


class SqliteZoteroGateway(ZoteroGateway, NotifyMixin):
    """
    Read-only implementation of ZoteroGateway using local zotero.sqlite.
    Uses a 'Shadow Copy' strategy to avoid locking the database.
    """

    def __init__(
        self,
        database_path: str,
        library_id: Optional[str] = None,
        library_type: Optional[str] = None,
    ):
        self._temp_db_path: Optional[str] = None
        # The configured library, used to scope the only writes this class
        # makes (item trash/restore, Issue #417).
        self.library_id = library_id
        self.library_type = library_type
        self._backed_up = False
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
        _warn_unscoped_once()

    def _get_connection(self) -> sqlite3.Connection:
        """This thread's connection to the shared shadow copy, kept open
        for the gateway's lifetime (Issue #436). Callers don't close it."""
        conn, path = _shadow_connection(self.original_db_path)
        self._temp_db_path = path
        return conn

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
                "dateAdded": row_dict.get("dateAdded") or "",
                "dateModified": row_dict.get("dateModified") or "",
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
        cursor = conn.execute(self._COLLECTION_SELECT)
        return [
            {
                "key": r["key"],
                "data": {"name": r["name"], "parentCollection": r["parentCollection"]},
                "meta": {"numItems": r["numItems"]},
            }
            for r in cursor
        ]

    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
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

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        """Resolves a collection key or name to one key (None if no match).
        Raises AmbiguousCollectionError when a name matches several
        collections, instead of silently taking the first (Issue #381)."""
        return resolve_collection_key(self.get_all_collections(), name)

    def _fetch_items_with_filter(
        self, filter_sql: str = "", params: tuple = (), trash_only: bool = False
    ) -> Iterator[ZoteroItem]:
        conn = self._get_connection()
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
                   i.dateAdded AS dateAdded, i.dateModified AS dateModified,
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
                clauses.append(f"({fields_sql} OR {self._MATCH_CREATORS_SQL} OR {note_sql})")
                params.extend([pattern, pattern, pattern, pattern])

        if query.item_type:
            negate, types = self._split_alternatives(query.item_type)
            if types:
                placeholders = ",".join("?" for _ in types)
                clauses.append(f"it.typeName {'NOT IN' if negate else 'IN'} ({placeholders})")
                params.extend(types)

        if query.tag:
            # Several tags must all match, like repeated `tag` parameters in the Web API.
            wanted = [query.tag] if isinstance(query.tag, str) else list(query.tag)
            for value in wanted:
                negate, tags = self._split_alternatives(value)
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

        if query.collection:
            clauses.append(
                "i.itemID IN (SELECT sci.itemID FROM collectionItems sci "
                "JOIN collections sc ON sci.collectionID = sc.collectionID WHERE sc.key = ?)"
            )
            params.append(query.collection)

        if query.since:
            clauses.append("i.version > ?")
            params.append(query.since)

        return "".join(f" AND {c}" for c in clauses), params

    # Zotero keeps its full-text index (FTS5) in a file next to zotero.sqlite.
    FULLTEXT_FILE = "fulltext.sqlite"

    @staticmethod
    def _fts_match(text: str) -> str:
        """Every word as a quoted FTS5 string, so a word like OR, NEAR or a stray quote is
        searched for, never read as query syntax. Quoted words are ANDed."""
        words = text.split()
        if not words:
            raise UsageError("Full-text search needs at least one word to look for.")
        return " ".join('"' + word.replace('"', '""') + '"' for word in words)

    def search_fulltext(
        self, text: str, query: Optional[ZoteroQuery] = None
    ) -> List[Tuple[ZoteroItem, float]]:
        """Ranked search of Zotero's own full-text index (Issue #560): items with a PDF
        containing every word, best first, scored by FTS5's bm25 (reported so that higher
        is better). Annotations and notes are not part of this index. A PDF counts for
        its parent item; a stand-alone PDF counts for itself."""
        index_path = os.path.join(os.path.dirname(self.original_db_path), self.FULLTEXT_FILE)
        if not os.path.exists(index_path):
            raise ConfigurationError(
                f"No {self.FULLTEXT_FILE} next to {os.path.basename(self.original_db_path)}. "
                "Full-text search reads the index newer Zotero versions keep in that file."
            )
        match = self._fts_match(text)
        index = _shadow_connection(index_path)[0]
        try:
            hits = index.execute(
                "SELECT rowid, bm25(fulltextContent) FROM fulltextContent "
                "WHERE fulltextContent MATCH ?",
                (match,),
            ).fetchall()
        except sqlite3.OperationalError as e:
            raise ConfigurationError(
                f"{self.FULLTEXT_FILE} has no usable full-text index ({e}). Full-text search "
                "needs a Zotero version that stores its index there."
            ) from e
        if not hits:
            return []

        conn = self._get_connection()
        targets = conn.execute(
            """
            SELECT att.itemID AS attachmentID, COALESCE(par.key, att.key) AS target
            FROM items att
            LEFT JOIN itemAttachments ia ON ia.itemID = att.itemID
            LEFT JOIN items par ON par.itemID = ia.parentItemID
            WHERE att.itemID IN (SELECT value FROM json_each(?))
              AND att.itemID NOT IN (SELECT itemID FROM deletedItems)
            """,
            (json.dumps([row[0] for row in hits]),),
        ).fetchall()
        target_of = {row["attachmentID"]: row["target"] for row in targets}
        best: Dict[str, float] = {}
        for item_id, rank in hits:
            target = target_of.get(item_id)
            if target is not None:
                best[target] = max(best.get(target, float("-inf")), -rank)

        filter_sql, params = self._search_filter(query or ZoteroQuery())
        # filter_sql is a fixed fragment with "?" placeholders from _search_filter; the
        # keys and every filter value are bound as parameters (nothing user-typed is
        # interpolated into the SQL).
        items = self._fetch_items_with_filter(
            filter_sql + " AND i.key IN (SELECT value FROM json_each(?))",  # nosec B608
            tuple(params) + (json.dumps(list(best)),),
        )
        ranked = [(item, best[item.key]) for item in items]
        ranked.sort(key=lambda pair: (-pair[1], pair[0].key))
        return ranked

    # Sort fields the offline search understands (a subset of the Web API's).
    SORT_FIELDS = ("date", "dateAdded", "dateModified", "title", "creator", "itemType")

    @staticmethod
    def _sort_value(item: ZoteroItem, field: str) -> str:
        if field == "date":
            return (item.date or "")[:10]
        if field == "dateAdded":
            return item.date_added or ""
        if field == "dateModified":
            return item.date_modified or ""
        if field == "title":
            return (item.title or "").lower()
        if field == "itemType":
            return item.item_type
        if field == "creator":
            for creator in item.creators:
                return str(creator.get("lastName") or creator.get("name") or "").lower()
        return ""

    def _sorted(self, items: List[ZoteroItem], query: ZoteroQuery) -> List[ZoteroItem]:
        """The Web API sorts server-side; offline does it here, with items that
        lack the field last whichever the direction."""
        field = query.sort
        if field not in self.SORT_FIELDS:
            return items
        present = [i for i in items if self._sort_value(i, field)]
        missing = [i for i in items if not self._sort_value(i, field)]
        present.sort(key=lambda i: self._sort_value(i, field), reverse=query.direction != "asc")
        return present + missing

    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        filter_sql, params = self._search_filter(query)
        return iter(
            self._sorted(list(self._fetch_items_with_filter(filter_sql, tuple(params))), query)
        )

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
        cursor = conn.execute("SELECT name FROM tags")
        return [r["name"] for r in cursor]

    def get_tags_for_item(self, item_key: str) -> List[str]:
        item = self.get_item(item_key)
        return item.tags if item else []

    # Zotero's itemAttachments.linkMode integers, as the Web API names them.
    _LINK_MODES = {
        0: "imported_file",
        1: "imported_url",
        2: "linked_file",
        3: "linked_url",
        4: "embedded_image",
    }

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        return self.get_children_by_parent([item_key]).get(item_key, [])

    def get_annotations(self, item_key: str) -> List[Dict[str, Any]]:
        """PDF annotations from `itemAnnotations`: of the attachment itself if `item_key`
        is one, else of each of the item's attachments (Issue #558). Trashed ones are
        left out, like the Web API's."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT i.itemID, it.typeName FROM items i "
            "JOIN itemTypes it ON i.itemTypeID = it.itemTypeID WHERE i.key = ?",
            (item_key,),
        ).fetchone()
        if row is None:
            return []
        if row["typeName"] == "attachment":
            parent_ids = [row["itemID"]]
        else:
            parent_ids = [
                r["itemID"]
                for r in conn.execute(
                    "SELECT itemID FROM itemAttachments WHERE parentItemID = ?", (row["itemID"],)
                )
            ]
        if not parent_ids:
            return []
        rows = conn.execute(
            """
            SELECT a.itemID, i.key, p.key AS attachment, a.type, a.text, a.comment, a.color,
                   a.pageLabel, a.sortIndex, i.dateAdded
            FROM itemAnnotations a
            JOIN items i ON i.itemID = a.itemID
            JOIN items p ON p.itemID = a.parentItemID
            WHERE a.parentItemID IN (SELECT value FROM json_each(?))
              AND a.itemID NOT IN (SELECT itemID FROM deletedItems)
            """,
            (json.dumps(parent_ids),),
        ).fetchall()
        tags_by_item: Dict[int, List[str]] = {}
        for tag_row in conn.execute(
            "SELECT itg.itemID, t.name FROM itemTags itg JOIN tags t ON itg.tagID = t.tagID "
            "WHERE itg.itemID IN (SELECT value FROM json_each(?))",
            (json.dumps([r["itemID"] for r in rows]),),
        ):
            tags_by_item.setdefault(tag_row["itemID"], []).append(tag_row["name"])
        found = [
            annotation_records.build(
                key=r["key"],
                attachment=r["attachment"],
                kind=annotation_records.SQLITE_TYPES.get(r["type"], str(r["type"])),
                text=r["text"],
                comment=r["comment"],
                color=r["color"],
                page=r["pageLabel"],
                tags=sorted(tags_by_item.get(r["itemID"], [])),
                date_added=r["dateAdded"],
                sort_index=r["sortIndex"],
            )
            for r in rows
        ]
        return annotation_records.in_reading_order(found)

    def get_children_by_parent(self, parent_keys: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        The notes and attachments of each parent, in the Web API's shape
        (`data.itemType`, `data.note`, `data.parentItem`, ...), from one
        query for all parents (Issue #437). Only keys used to be returned,
        so every SDB decision read offline was empty: `slr report status`
        showed 0 accepted and 0 rejected.

        No items.parentItemID in the real schema -- child linkage lives on
        itemAttachments/itemNotes instead (see _TOP_LEVEL_ONLY_SQL above).
        The keys go in as one JSON parameter, not one "?" each (#422).
        """
        if not parent_keys:
            return {}
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT c.itemID, c.key, c.version, c.dateAdded, c.dateModified,
                   it.typeName, p.key AS parentKey,
                   n.note, a.linkMode, a.contentType, a.path,
                   (SELECT dv.value FROM itemData d
                    JOIN fields f ON d.fieldID = f.fieldID
                    JOIN itemDataValues dv ON d.valueID = dv.valueID
                    WHERE d.itemID = c.itemID AND f.fieldName = 'title') AS title,
                   (SELECT dv.value FROM itemData d
                    JOIN fields f ON d.fieldID = f.fieldID
                    JOIN itemDataValues dv ON d.valueID = dv.valueID
                    WHERE d.itemID = c.itemID AND f.fieldName = 'url') AS url
            FROM items c
            JOIN itemTypes it ON c.itemTypeID = it.itemTypeID
            LEFT JOIN itemNotes n ON n.itemID = c.itemID
            LEFT JOIN itemAttachments a ON a.itemID = c.itemID
            JOIN items p ON p.itemID = COALESCE(n.parentItemID, a.parentItemID)
            WHERE p.key IN (SELECT value FROM json_each(?))
              AND c.itemID NOT IN (SELECT itemID FROM deletedItems)
            ORDER BY c.itemID
            """,
            (json.dumps(list(parent_keys)),),
        ).fetchall()
        if not rows:
            return {}

        tags: Dict[int, List[Dict[str, Any]]] = {}
        child_ids = json.dumps([r["itemID"] for r in rows])
        for t in conn.execute(
            """
            SELECT itg.itemID, tg.name FROM itemTags itg JOIN tags tg ON itg.tagID = tg.tagID
            WHERE itg.itemID IN (SELECT value FROM json_each(?))
            """,
            (child_ids,),
        ):
            tags.setdefault(t["itemID"], []).append({"tag": t["name"]})

        children: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            data: Dict[str, Any] = {
                "key": r["key"],
                "version": r["version"],
                "itemType": r["typeName"],
                "parentItem": r["parentKey"],
                "dateAdded": r["dateAdded"],
                "dateModified": r["dateModified"],
                "tags": tags.get(r["itemID"], []),
            }
            if r["typeName"] == "note":
                data["note"] = r["note"] or ""
            else:
                data.update(self._attachment_fields(r))
            children.setdefault(r["parentKey"], []).append(
                {"key": r["key"], "version": r["version"], "data": data}
            )
        return children

    @classmethod
    def _attachment_fields(cls, row: sqlite3.Row) -> Dict[str, Any]:
        link_mode = cls._LINK_MODES.get(row["linkMode"], "imported_file")
        fields: Dict[str, Any] = {
            "linkMode": link_mode,
            "title": row["title"] or "",
            "contentType": row["contentType"] or "",
        }
        path = row["path"] or ""
        if path.startswith(STORAGE_PREFIX):
            fields["filename"] = path[len(STORAGE_PREFIX) :]
        elif path:
            fields["path"] = path
        if row["url"]:
            fields["url"] = row["url"]
        return fields

    # --- Write Operations (FORBIDDEN in Offline mode) ---

    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        raise OfflineReadOnly()

    def get_item_template(self, item_type: str) -> Dict[str, Any]:
        raise OfflineReadOnly()

    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        raise OfflineReadOnly()

    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        raise OfflineReadOnly()

    def update_items(self, items_data: List[Dict[str, Any]]) -> bool:
        raise OfflineReadOnly()

    def delete_item(self, item_key: str, version: int) -> bool:
        raise OfflineReadOnly()

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        raise OfflineReadOnly()

    def delete_collection(self, collection_key: str, version: int) -> bool:
        raise OfflineReadOnly()

    def rename_collection(self, collection_key: str, version: int, name: str) -> bool:
        raise OfflineReadOnly()

    def add_tags(self, item_key: str, tags: List[str]) -> bool:
        raise OfflineReadOnly()

    def delete_tags(self, tags: List[str], version: int) -> bool:
        raise OfflineReadOnly()

    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        raise OfflineReadOnly()

    def update_note(
        self, note_key: str, version: int, note_content: str, parent_item_key: Optional[str] = None
    ) -> bool:
        raise OfflineReadOnly()

    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        raise OfflineReadOnly()

    def upload_attachment(
        self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf"
    ) -> bool:
        raise OfflineReadOnly()

    def download_attachment(self, item_key: str, save_path: str) -> bool:
        """Copy an attachment's file from Zotero's own `storage/<KEY>/` folder (or a
        linked file's absolute path) to `save_path`. A read, so allowed offline; False,
        with a reason, when the file isn't on this machine."""
        source = self._attachment_file(item_key)
        if source is None:
            return False
        shutil.copyfile(source, save_path)
        return True

    def _attachment_file(self, item_key: str) -> Optional[str]:
        row = (
            self._get_connection()
            .execute(
                "SELECT a.linkMode, a.path FROM itemAttachments a "
                "JOIN items i ON i.itemID = a.itemID WHERE i.key = ?",
                (item_key,),
            )
            .fetchone()
        )
        path = (row["path"] or "") if row else ""
        if not path:
            self._say(f"No file recorded for attachment {item_key}.", logging.WARNING)
            return None
        if path.startswith(STORAGE_PREFIX):
            folder = os.path.realpath(
                os.path.join(os.path.dirname(self.original_db_path), "storage", item_key)
            )
            source = os.path.realpath(os.path.join(folder, path[len(STORAGE_PREFIX) :]))
            if os.path.commonpath([folder, source]) != folder:
                self._say(
                    f"Attachment {item_key} points outside its storage folder.", logging.WARNING
                )
                return None
        elif os.path.isabs(path):
            source = path
        else:
            self._say(
                f"Attachment {item_key} is stored relative to a base directory ({path}); "
                "its location isn't known offline.",
                logging.WARNING,
            )
            return None
        if not os.path.isfile(source):
            self._say(
                f"The file for attachment {item_key} is not on this machine: {source}",
                logging.WARNING,
            )
            return None
        return source

    def update_attachment_link(self, item_key: str, version: int, new_path: str) -> bool:
        raise OfflineReadOnly()

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
        NOT _get_connection()'s shadow copy, which is deleted at exit and
        would silently discard any write made through it. `timeout` sets
        SQLite's busy-retry window so a momentary lock (e.g. Desktop mid-write)
        is retried rather than failing immediately.
        """
        conn = sqlite3.connect(self.original_db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row
        return conn

    def _local_library_id(self, conn: sqlite3.Connection) -> Optional[int]:
        """The zotero.sqlite libraryID of the configured library, or None
        when it can't be determined (no library configured, or an older
        schema without the libraries/groups tables)."""
        try:
            if self.library_type == "group" and self.library_id:
                row = conn.execute(
                    "SELECT libraryID FROM groups WHERE groupID = ?", (int(self.library_id),)
                ).fetchone()
            elif self.library_type == "user":
                row = conn.execute("SELECT libraryID FROM libraries WHERE type = 'user'").fetchone()
            else:
                return None
        except (sqlite3.OperationalError, ValueError):
            return None
        return int(row["libraryID"]) if row else None

    def _find_item_for_write(self, conn: sqlite3.Connection, item_key: str) -> Optional[int]:
        """The itemID to write to. Scoped to the configured library when it
        can be determined; otherwise a key found in more than one library is
        refused rather than guessed (Issue #417: keys are unique per library
        only, and the first match used to be trashed)."""
        library = self._local_library_id(conn)
        if library is not None:
            row = conn.execute(
                "SELECT itemID FROM items WHERE key = ? AND libraryID = ?", (item_key, library)
            ).fetchone()
            return int(row["itemID"]) if row else None
        rows = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchall()
        if len(rows) > 1:
            raise RuntimeError(
                f"Item key {item_key} exists in {len(rows)} locally synced libraries and the "
                "configured library couldn't be matched in zotero.sqlite; refusing to guess. "
                "Use online mode (without --offline) for this item."
            )
        return int(rows[0]["itemID"]) if rows else None

    def _backup_before_first_write(self) -> None:
        """Copies zotero.sqlite to `zotero.sqlite.zotero-cli-bak` before the
        first write of this run (Issue #417). Uses SQLite's backup API, so
        the copy is consistent even if Zotero has the file open."""
        if self._backed_up:
            return
        backup_path = f"{self.original_db_path}.zotero-cli-bak"
        src = sqlite3.connect(self.original_db_path, timeout=5.0)
        try:
            fd = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.close(fd)
            dst = sqlite3.connect(backup_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        self._backed_up = True
        self._say(f"Backed up zotero.sqlite to {backup_path} before writing.")

    def trash_item(self, item_key: str, version: int = 0) -> bool:
        """
        Moves an item to the trash, matching Desktop's Zotero.Items.trash():
        bumps dateModified/clientDateModified, marks the row dirty (synced=0)
        so Desktop's next sync pushes the deletion to the server, and adds a
        deletedItems row. Idempotent (INSERT OR IGNORE), same as Desktop's own
        query. Returns False if no item with this key exists.
        """
        conn = self._get_write_connection()
        try:
            item_id = self._find_item_for_write(conn, item_key)
            if item_id is None:
                return False
            self._backup_before_first_write()
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

    def restore_item(self, item_key: str, version: int = 0) -> bool:
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
            item_id = self._find_item_for_write(conn, item_key)
            if item_id is None:
                return False
            self._backup_before_first_write()
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

    def count_items(self) -> int:
        """Items in the local database, for `system check` (Issue #382)."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT COUNT(*) FROM items WHERE itemID NOT IN (SELECT itemID FROM deletedItems)"
        ).fetchone()
        return int(row[0])

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
                existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
                if "library_id" not in existing_columns:
                    conn.execute("ALTER TABLE jobs ADD COLUMN library_id TEXT")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_task_status ON jobs (task_type, status)"
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
