"""
Resolves a collection argument (key or name) to exactly one collection key
(Issue #381).

Names aren't unique in Zotero: the SLR workflow creates identically named
phase folders (`2-full_text`, ...) under every source, and libraries often
have several "Included" or "Excluded" folders. Taking the first match meant
a command could empty or delete the wrong collection, so an ambiguous name
is now an error that lists the candidates, and the user passes a key.
"""

from typing import Any, Dict, List, Optional, Sequence

from zotero_cli.core.exceptions import AmbiguousCollectionError


def _name(collection: Dict[str, Any]) -> str:
    return str(collection.get("data", {}).get("name", ""))


def collection_path(collection: Dict[str, Any], by_key: Dict[str, Dict[str, Any]]) -> str:
    """"Parent / Child / Name" for display, following parentCollection."""
    parts: List[str] = [_name(collection)]
    parent = collection.get("data", {}).get("parentCollection")
    seen = {collection.get("key")}
    while parent and parent in by_key and parent not in seen:
        seen.add(parent)
        parts.append(_name(by_key[parent]))
        parent = by_key[parent].get("data", {}).get("parentCollection")
    return " / ".join(reversed(parts))


def resolve_collection_key(
    collections: Sequence[Dict[str, Any]], name_or_key: str
) -> Optional[str]:
    """
    Returns the key of the one collection `name_or_key` refers to, or None
    if none matches. Tries, in order: an existing key, an exact name, a
    case-insensitive name. Raises AmbiguousCollectionError when a name
    matches more than one collection.
    """
    if not name_or_key:
        return None
    by_key = {str(c.get("key")): c for c in collections}
    if name_or_key in by_key:
        return name_or_key

    for matches in (
        [c for c in collections if _name(c) == name_or_key],
        [c for c in collections if _name(c).casefold() == name_or_key.casefold()],
    ):
        if len(matches) == 1:
            return str(matches[0]["key"])
        if len(matches) > 1:
            candidates = sorted(
                (str(c["key"]), collection_path(c, by_key)) for c in matches
            )
            raise AmbiguousCollectionError(name_or_key, candidates)
    return None
