import os
import shutil
import sqlite3
import tempfile
from typing import Any, Dict, Iterator, List, Optional

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ResearchPaper, ZoteroQuery
from zotero_cli.core.zotero_item import ZoteroItem


class ConfigurationError(Exception):
    """Raised when an operation is not permitted in the current configuration."""
    pass


class SqliteZoteroGateway(ZoteroGateway):
    """
    Read-only implementation of ZoteroGateway using local zotero.sqlite.
    Uses a 'Shadow Copy' strategy to avoid locking the database.
    """

    def __init__(self, database_path: str):
        if not database_path or not os.path.exists(database_path):
            raise ConfigurationError(f"Zotero database not found at: {database_path}")
        self.original_db_path = database_path
        self._temp_db_path: Optional[str] = None

    def _get_connection(self) -> sqlite3.Connection:
        # Create shadow copy
        if not self._temp_db_path:
            temp_dir = tempfile.gettempdir()
            self._temp_db_path = os.path.join(temp_dir, f"zotero_cli_shadow_{os.getpid()}.sqlite")
            shutil.copy2(self.original_db_path, self._temp_db_path)

        conn = sqlite3.connect(self._temp_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def __del__(self):
        if self._temp_db_path and os.path.exists(self._temp_db_path):
            try:
                os.remove(self._temp_db_path)
            except:
                pass

    def _map_row_to_item(self, row: sqlite3.Row, creators: List[Dict[str, Any]], collections: List[str], tags: List[str]) -> ZoteroItem:
        row_dict = dict(row)
        raw_item = {
            "key": row_dict["key"],
            "version": row_dict["version"],
            "libraryID": row_dict["libraryID"],
            "data": {
                "key": row_dict["key"],
                "version": row_dict["version"],
                "itemType": row_dict["typeName"],
                "title": row_dict.get("title") or "",
                "abstractNote": row_dict.get("abstractNote") or "",
                "date": row_dict.get("date") or "",
                "DOI": row_dict.get("DOI") or "",
                "url": row_dict.get("url") or "",
                "extra": row_dict.get("extra") or "",
                "creators": creators,
                "collections": collections,
                "tags": [{"tag": t} for t in tags],
            }
        }
        return ZoteroItem.from_raw_zotero_item(raw_item)

    # --- Read Operations ---

    def get_all_collections(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT c.key, c.parentCollection, cd.name
                FROM collections c
                JOIN collectionData cd ON c.collectionID = cd.collectionID
            """)
            return [{"key": r["key"], "data": {"name": r["name"], "parentCollection": r["parentCollection"]}} for r in cursor]

    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT c.key, c.parentCollection, cd.name
                FROM collections c
                JOIN collectionData cd ON c.collectionID = cd.collectionID
                WHERE c.key = ?
            """, (collection_key,)).fetchone()
            if row:
                return {"key": row["key"], "data": {"name": row["name"], "parentCollection": row["parentCollection"]}}
            return None

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        cols = self.get_all_collections()
        for c in cols:
            if c.get("data", {}).get("name") == name:
                return str(c["key"])
        return None

    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        # Basic implementation of search
        # Note: A full implementation would require complex SQL to match tags, collections, etc.
        # For MVP, we fetch all items and filter in Python if needed, or implement specific joins.
        with self._get_connection() as conn:
            # This is a simplified query for the MVP
            # It joins items with their type and basic metadata fields
            query_sql = """
                SELECT i.key, i.version, i.libraryID, it.typeName,
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
                WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
                GROUP BY i.itemID
            """
            cursor = conn.execute(query_sql)
            for row in cursor:
                # Fetch creators for this item
                creator_cursor = conn.execute("""
                    SELECT cd.firstName, cd.lastName, ct.creatorType
                    FROM itemCreators ic
                    JOIN creators c ON ic.creatorID = c.creatorID
                    JOIN creatorData cd ON c.creatorDataID = cd.creatorDataID
                    JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
                    WHERE ic.itemID = (SELECT itemID FROM items WHERE key = ?)
                    ORDER BY ic.orderIndex
                """, (row["key"],))
                creators = [{"creatorType": r["creatorType"], "firstName": r["firstName"], "lastName": r["lastName"]} for r in creator_cursor]

                # Fetch collections
                col_cursor = conn.execute("""
                    SELECT c.key
                    FROM collectionItems ci
                    JOIN collections c ON ci.collectionID = c.collectionID
                    WHERE ci.itemID = (SELECT itemID FROM items WHERE key = ?)
                """, (row["key"],))
                collections = [r["key"] for r in col_cursor]

                # Fetch tags
                tag_cursor = conn.execute("""
                    SELECT t.name
                    FROM itemTags it
                    JOIN tags t ON it.tagID = t.tagID
                    WHERE it.itemID = (SELECT itemID FROM items WHERE key = ?)
                """, (row["key"],))
                tags = [r["name"] for r in tag_cursor]

                yield self._map_row_to_item(row, creators, collections, tags)

    def get_items_in_collection(self, collection_id: str, top_only: bool = False) -> Iterator[ZoteroItem]:
        # Reuse search_items but filter by collection
        # For better performance, this should be a direct SQL query
        for item in self.search_items(ZoteroQuery()):
            if collection_id in item.collections:
                yield item

    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        for item in self.search_items(ZoteroQuery()):
            if item.key == item_key:
                return item
        return None

    def get_tags(self) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT name FROM tags")
            return [r["name"] for r in cursor]

    def get_tags_for_item(self, item_key: str) -> List[str]:
        item = self.get_item(item_key)
        return item.tags if item else []

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        # Simplified: items with parentItem = itemID of item_key
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT key FROM items 
                WHERE parentItemID = (SELECT itemID FROM items WHERE key = ?)
            """, (item_key,))
            return [{"key": r["key"]} for r in cursor]

    # --- Write Operations (FORBIDDEN) ---

    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        raise ConfigurationError("Offline mode is read-only")

    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def delete_item(self, item_key: str, version: int) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        raise ConfigurationError("Offline mode is read-only")

    def delete_collection(self, collection_key: str, version: int) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def rename_collection(self, collection_key: str, version: int, name: str) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def add_tags(self, item_key: str, tags: List[str]) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def delete_tags(self, tags: List[str], version: int) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def update_note(self, note_key: str, version: int, note_content: str) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def upload_attachment(self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf") -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def download_attachment(self, item_key: str, save_path: str) -> bool:
        # Attachment download might be possible if files are local, but for now we follow 'read-only' mandate for DB
        raise ConfigurationError("Offline mode is read-only (local file access not implemented)")

    def update_attachment_link(self, item_key: str, version: int, new_path: str) -> bool:
        raise ConfigurationError("Offline mode is read-only")

    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        for item in self.search_items(ZoteroQuery()):
            if tag in item.tags:
                yield item

    def verify_credentials(self) -> bool:
        """
        Verifies that the database file exists and is accessible.
        """
        return os.path.exists(self.original_db_path)
