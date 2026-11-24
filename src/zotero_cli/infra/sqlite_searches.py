"""Saved searches from the local `zotero.sqlite`, in the Web API's shape (Issue #663)."""

import sqlite3
from typing import Any, Dict, List

_SEARCHES_SQL = (
    "SELECT savedSearchID, key, version, savedSearchName FROM savedSearches "
    "WHERE savedSearchID NOT IN (SELECT savedSearchID FROM deletedSearches) "
    "ORDER BY savedSearchID"
)
_CONDITIONS_SQL = (
    "SELECT savedSearchID, condition, operator, value FROM savedSearchConditions "
    "ORDER BY savedSearchID, searchConditionID"
)


def read_saved_searches(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Best effort: the database's search conditions carry a `mode` the API shape has no
    place for, which is left out; a database without the search tables has no searches."""
    try:
        searches = conn.execute(_SEARCHES_SQL).fetchall()
        conditions = conn.execute(_CONDITIONS_SQL).fetchall()
    except sqlite3.OperationalError:
        return []
    by_search: Dict[int, List[Dict[str, Any]]] = {}
    for row in conditions:
        by_search.setdefault(row["savedSearchID"], []).append(
            {"condition": row["condition"], "operator": row["operator"], "value": row["value"]}
        )
    return [
        {
            "key": row["key"],
            "version": row["version"],
            "data": {
                "key": row["key"],
                "version": row["version"],
                "name": row["savedSearchName"],
                "conditions": by_search.get(row["savedSearchID"], []),
            },
        }
        for row in searches
    ]
