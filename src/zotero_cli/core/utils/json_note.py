import html
import json
import re
from typing import Any, Optional


def decode_json_note(content: str) -> Optional[Any]:
    """Parses the JSON body of a note that stores JSON, HTML-escaped inside a
    <div> (an application's own record kept in a Zotero note). Returns None if
    there's no valid JSON object, so a plain note is left as text."""
    if not content:
        return None
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if not json_match:
        return None
    try:
        return json.loads(html.unescape(json_match.group(0)))
    except json.JSONDecodeError:
        return None
