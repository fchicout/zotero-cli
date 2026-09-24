import html
import json
import re
from typing import Any, Dict, Optional


def encode_json_note(data: Any) -> str:
    """
    Serializes `data` as the body of a Zotero note: JSON, HTML-escaped,
    inside a <div>. Without the escaping, a `<` or `>` in a free-text field
    (a screening reason, extraction evidence) is read as HTML by Zotero's
    note sanitizer, which can drop or rewrite part of the stored record.
    `parse_sdb_note`/`decode_json_note` reverse it.
    """
    return f"<div>{html.escape(json.dumps(data, indent=2), quote=False)}</div>"


def decode_json_note(content: str) -> Optional[Any]:
    """Parses the JSON body of a note written by `encode_json_note` (or by
    an older version, which didn't escape it). Returns None if there's no
    valid JSON object."""
    if not content:
        return None
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if not json_match:
        return None
    try:
        return json.loads(html.unescape(json_match.group(0)))
    except json.JSONDecodeError:
        return None


def parse_sdb_note(content: str) -> Optional[Dict[str, Any]]:
    """
    Robustly parses SDB JSON metadata from a note string.
    1. Strips HTML tags (e.g. <div>, <br>).
    2. Uses Regex to find the JSON block.
    3. Parses JSON and validates SDB markers.

    Returns the parsed dict if valid SDB data, else None.
    """
    data = decode_json_note(content)
    if not isinstance(data, dict):
        return None

    # 3. Validate SDB markers
    # Must have at least one of these keys to be considered an SDB note
    is_sdb = (
        data.get("action") == "screening_decision"
        or "audit_version" in data
        or "sdb_version" in data
    )

    if is_sdb and isinstance(data, dict):
        return data

    return None
