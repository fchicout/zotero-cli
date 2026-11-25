"""The one reading of a `Retry-After` header (Issue #711, from #611).

The header holds delta-seconds or an HTTP date. The metadata clients, Zotero's client and the
network gateway each used to read it their own way."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional


def parse_retry_after(value: Any) -> Optional[float]:
    """Seconds the header asks for, or None when it is absent, unreadable or negative.

    A date that has already passed is not an error: it asks for no wait (0.0)."""
    if value is None or value == "":
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        pass
    else:
        return seconds if seconds >= 0 else None
    try:
        when = parsedate_to_datetime(str(value))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
