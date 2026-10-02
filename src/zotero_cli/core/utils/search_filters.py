"""Client-side filters for `search`: publication year and date added (Issue #562).

Zotero's own `since` parameter is a library *version*, not a date, and the Web API
has no date-range filter, so these run on the items as they stream in.
"""

import re
from datetime import date
from typing import Optional, Tuple

from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.zotero_item import ZoteroItem

YearRange = Tuple[Optional[int], Optional[int]]

_YEAR = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def parse_year_range(text: str) -> YearRange:
    """`2020`, `2018-2022`, `2018-` (from) or `-2022` (until), as (low, high)."""
    value = text.strip()
    match = re.fullmatch(r"(\d{4})?\s*-?\s*(\d{4})?", value)
    if not value or not match or not (match.group(1) or match.group(2)):
        raise UsageError(f"--year takes a year or a range like 2018-2022, not '{text}'.")
    low, high = match.group(1), match.group(2)
    if "-" not in value:  # a single year
        return int(low), int(low)
    result = (int(low) if low else None, int(high) if high else None)
    if result[0] is not None and result[1] is not None and result[0] > result[1]:
        raise UsageError(f"--year range '{text}' ends before it starts.")
    return result


def parse_day(text: str, flag: str) -> str:
    """A `YYYY-MM-DD` date, validated, as the same ISO string."""
    try:
        return date.fromisoformat(text.strip()).isoformat()
    except ValueError:
        raise UsageError(f"{flag} takes a date like 2026-01-31, not '{text}'.") from None


def item_year(item: ZoteroItem) -> Optional[int]:
    match = _YEAR.search(item.date or "")
    return int(match.group(1)) if match else None


def matches(
    item: ZoteroItem,
    years: Optional[YearRange] = None,
    added_since: Optional[str] = None,
    added_until: Optional[str] = None,
) -> bool:
    """True if the item passes every filter that was given. An item with no
    year (or no date added) never passes a filter on it."""
    if years is not None:
        year = item_year(item)
        low, high = years
        if year is None or (low is not None and year < low) or (high is not None and year > high):
            return False
    if added_since is not None or added_until is not None:
        added = (item.date_added or "")[:10]
        if not added:
            return False
        if added_since is not None and added < added_since:
            return False
        if added_until is not None and added > added_until:
            return False
    return True
