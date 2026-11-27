"""The items a restore creates from what an archive holds: notes, attachments and
annotations."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

IMAGE_KEY = re.compile(r'data-attachment-key="([A-Z0-9]{8})"')


def note_payload(
    data: dict, parent: Optional[str] = None, collections: Optional[List[str]] = None
) -> dict:
    """A note created from what the archive holds about it (Issue #682): its text and its tags,
    with their types, under the new parent or in the mapped collections. `create_note` only
    ever sent the text."""
    payload: dict = {"itemType": "note", "note": data.get("note", ""), "tags": data.get("tags", [])}
    if parent:
        payload["parentItem"] = parent
    if collections is not None:
        payload["collections"] = collections
    if data.get("deleted"):
        payload["deleted"] = 1  # the Web API honours it on create (checked on a test library)
    payload.update({k: data[k] for k in ("dateAdded", "dateModified") if data.get(k)})
    if IMAGE_KEY.search(data.get("note", "")):
        # Edited right after (to name the new images): the API keeps a modification date that
        # equals the stored one as "unchanged" and stamps the edit, so it is sent then, when
        # it differs (Issue #704, checked on a test library).
        payload.pop("dateModified", None)
    return payload


# What an archived attachment has that a new one must not carry over: its identity and
# bookkeeping (the relations are set later, #686; the dates are kept, #687).
_ATTACHMENT_LOCAL = {
    "key",
    "version",
    "parentItem",
    "collections",
    "relations",
    "md5",
    "mtime",
    "deleted",
}


def attachment_payload(data: dict, collections: Optional[List[str]] = None) -> Dict[str, Any]:
    """An attachment created from what the archive holds about it (Issue #684): title, file name,
    content type, link mode (`imported_file` or `imported_url`), url, access date, tags. The
    upload used to name everything after its temporary file."""
    payload = {k: v for k, v in data.items() if k not in _ATTACHMENT_LOCAL}
    payload.setdefault("title", "")  # never the upload's default, the temporary file's name
    if collections is not None:
        payload["collections"] = collections
    if data.get("deleted"):
        payload["deleted"] = 1
    return payload


def annotation_payload(data: dict, parent: str) -> Dict[str, Any]:
    """An annotation created from what the archive holds about it, under the restored PDF
    (Issue #685): type, text, comment, colour, page label, sort index, position and tags (the
    real API takes all of these as they were archived, checked on a test library)."""
    payload = {k: v for k, v in data.items() if k not in _ATTACHMENT_LOCAL}
    payload["parentItem"] = parent
    if data.get("deleted"):
        payload["deleted"] = 1
    return payload
