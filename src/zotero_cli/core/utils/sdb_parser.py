import json
import re
from typing import Optional, Dict, Any

def parse_sdb_note(content: str) -> Optional[Dict[str, Any]]:
    """
    Robustly parses SDB JSON metadata from a note string.
    1. Strips HTML tags (e.g. <div>, <br>).
    2. Uses Regex to find the JSON block.
    3. Parses JSON and validates SDB markers.
    
    Returns the parsed dict if valid SDB data, else None.
    """
    if not content:
        return None

    # 1. Regex to find the JSON block { ... }
    # DOTALL allows dot to match newlines
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    
    if not json_match:
        return None
    
    json_str = json_match.group(0)
    
    # 2. Parse JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None
        
    # 3. Validate SDB markers
    # Must have at least one of these keys to be considered an SDB note
    is_sdb = (
        data.get("action") == "screening_decision"
        or "audit_version" in data
        or "sdb_version" in data
    )
    
    if is_sdb:
        return data
        
    return None
