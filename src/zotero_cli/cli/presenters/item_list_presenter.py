"""Field projection and output formats for `item list` (Issue #323)."""

import re
from typing import Any, Callable, Dict, List, Optional, Sequence, TextIO

from zotero_cli.cli.presenters import records
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.zotero_item import ZoteroItem

DEFAULT_FIELDS = ["key", "title", "type"]
WIDE_FIELDS = ["key", "title", "first_author", "year", "venue", "doi"]
FORMATS = ["table", "json", "csv", "ndjson", "keys", "markdown"]  # item list also offers markdown

# Zotero stores a work's venue under a different field per item type.
VENUE_FIELDS = ("publicationTitle", "proceedingsTitle", "conferenceName", "bookTitle")

FieldValue = Any  # str, or List[str] for multi-valued fields


def _data(item: ZoteroItem) -> Dict[str, Any]:
    data = item.raw_data.get("data", {})
    return data if isinstance(data, dict) else {}


def _creator_name(creator: Dict[str, Any]) -> str:
    if creator.get("name"):
        return str(creator["name"])
    first, last = creator.get("firstName", ""), creator.get("lastName", "")
    return f"{last}, {first}" if first and last else (last or first)


def _first_author(item: ZoteroItem) -> str:
    creators = [c for c in item.creators if c.get("creatorType", "author") == "author"]
    if not creators:
        return ""
    lead = creators[0].get("lastName") or creators[0].get("name") or ""
    return f"{lead} et al." if len(creators) > 1 else str(lead)


def _year(item: ZoteroItem) -> str:
    match = re.search(r"\b(\d{4})\b", item.date or "")
    return match.group(1) if match else ""


def _venue(item: ZoteroItem) -> str:
    data = _data(item)
    return next((str(data[f]) for f in VENUE_FIELDS if data.get(f)), "")


# Friendly field name -> (column label, extractor). Anything not listed here
# falls back to a raw Zotero field of that name, e.g. `volume` or `ISSN`.
_KNOWN_FIELDS: Dict[str, "tuple[str, Callable[[ZoteroItem], FieldValue]]"] = {
    "key": ("Key", lambda i: i.key),
    "title": ("Title", lambda i: i.title or "Untitled"),
    "type": ("Type", lambda i: i.item_type),
    "creators": ("Creators", lambda i: [_creator_name(c) for c in i.creators]),
    "first_author": ("First Author", _first_author),
    "date": ("Date", lambda i: i.date or ""),
    "year": ("Year", _year),
    "venue": ("Venue", _venue),
    "doi": ("DOI", lambda i: i.doi or ""),
    "url": ("URL", lambda i: i.url or ""),
    "abstract": ("Abstract", lambda i: i.abstract or ""),
    "extra": ("Extra", lambda i: i.extra or ""),
    "tags": ("Tags", lambda i: list(i.tags)),
    "collections": ("Collections", lambda i: list(i.collections)),
    "parent": ("Parent", lambda i: i.parent_item or ""),
    "date_added": ("Date Added", lambda i: i.date_added or ""),
    "date_modified": ("Date Modified", lambda i: i.date_modified or ""),
}


def parse_fields(spec: Optional[str], wide: bool = False) -> List[str]:
    """Turns a `--fields` value (or the `--wide` preset) into field names.
    Friendly names are case-insensitive; raw Zotero field names are kept as
    typed so they match the item data exactly."""
    if not spec:
        return list(WIDE_FIELDS if wide else DEFAULT_FIELDS)
    fields = []
    for name in (part.strip() for part in spec.split(",")):
        if name:
            fields.append(name.lower() if name.lower() in _KNOWN_FIELDS else name)
    return fields


def resolve_field(item: ZoteroItem, name: str) -> FieldValue:
    known = _KNOWN_FIELDS.get(name)
    if known:
        return known[1](item)
    data = _data(item)
    if name in data:
        value = data[name]
    else:
        # Tolerate case differences for raw fields too, e.g. `issn` -> `ISSN`.
        match = next((k for k in data if k.lower() == name.lower()), None)
        value = data[match] if match else ""
    return "" if value is None else value


def label(name: str) -> str:
    known = _KNOWN_FIELDS.get(name)
    return known[0] if known else name


def unknown_fields(items: Sequence[ZoteroItem], fields: Sequence[str]) -> List[str]:
    """Raw field names that no listed item has - most likely typos."""
    raw = [f for f in fields if f not in _KNOWN_FIELDS]
    if not raw:
        return []
    present = {k.lower() for item in items for k in _data(item)}
    return [f for f in raw if f.lower() not in present]


def _records(items: Sequence[ZoteroItem], fields: Sequence[str]) -> List[Dict[str, FieldValue]]:
    return [{f: resolve_field(item, f) for f in fields} for item in items]


def _columns(fields: Sequence[str]) -> List[records.Column]:
    return [records.Column(f, label(f), style="cyan" if f == "key" else None) for f in fields]


def render_table(
    items: Sequence[ZoteroItem], fields: Sequence[str], title: str, console: Console
) -> None:
    records.render_table(
        _records(items, fields),
        _columns(fields),
        title,
        console,
        footer=f"Showing {len(items)} items.",
    )


def render_json(items: Sequence[ZoteroItem], fields: Sequence[str], out: TextIO) -> None:
    records.render_json(_records(items, fields), _columns(fields), out)


def render_csv(items: Sequence[ZoteroItem], fields: Sequence[str], out: TextIO) -> None:
    records.render_csv(_records(items, fields), _columns(fields), out)


def render_markdown(items: Sequence[ZoteroItem], fields: Sequence[str], out: TextIO) -> None:
    records.render_markdown(_records(items, fields), _columns(fields), out)


def render(
    items: Sequence[ZoteroItem],
    fields: Sequence[str],
    fmt: str,
    title: str,
    console: Console,
    out: Optional[TextIO] = None,
) -> None:
    if fmt == "table":
        render_table(items, fields, title, console)
        return
    records.render_data(_records(items, fields), _columns(fields), fmt, out)
