"""The client-side search filters (Issue #562)."""

from typing import Optional

import pytest

from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.utils import search_filters
from zotero_cli.core.zotero_item import ZoteroItem


def _item(date: Optional[str] = None, added: Optional[str] = None) -> ZoteroItem:
    return ZoteroItem(
        key="K", version=1, item_type="journalArticle", title="T", date=date, date_added=added
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2020", (2020, 2020)),
        (" 2020 ", (2020, 2020)),
        ("2018-2022", (2018, 2022)),
        ("2018-", (2018, None)),
        ("-2022", (None, 2022)),
        ("2020-2020", (2020, 2020)),
    ],
)
def test_year_ranges(text: str, expected: tuple) -> None:
    assert search_filters.parse_year_range(text) == expected


@pytest.mark.parametrize("text", ["", "-", "abc", "20", "2018-2017", "2018-2020-2022", "20.20"])
def test_bad_year_ranges_are_usage_errors(text: str) -> None:
    with pytest.raises(UsageError, match="--year"):
        search_filters.parse_year_range(text)


def test_days_are_validated_and_normalised() -> None:
    assert search_filters.parse_day("2026-01-31", "--added-since") == "2026-01-31"
    assert search_filters.parse_day(" 2026-01-05 ", "--added-since") == "2026-01-05"


@pytest.mark.parametrize("text", ["2026-13-01", "yesterday", "2026-02-30", ""])
def test_bad_days_name_the_flag(text: str) -> None:
    with pytest.raises(UsageError, match="--added-until"):
        search_filters.parse_day(text, "--added-until")


@pytest.mark.parametrize(
    ("date", "year"),
    [
        ("2021-05-01", 2021),
        ("May 2021", 2021),
        ("2021", 2021),
        ("2021-05-01 May 1, 2021", 2021),
        ("c. 1999", 1999),
        ("", None),
        (None, None),
        ("no year here", None),
        ("12345", None),
    ],
)
def test_item_year(date: Optional[str], year: Optional[int]) -> None:
    assert search_filters.item_year(_item(date)) == year


def test_matching_by_year() -> None:
    assert search_filters.matches(_item("2020"), years=(2018, 2022))
    assert search_filters.matches(_item("2018"), years=(2018, None))
    assert not search_filters.matches(_item("2017"), years=(2018, None))
    assert not search_filters.matches(_item("2023"), years=(None, 2022))
    assert not search_filters.matches(_item(None), years=(2018, 2022))  # no year, never matches


def test_matching_by_date_added_uses_the_day_only() -> None:
    item = _item(added="2026-03-15T09:30:00Z")
    assert search_filters.matches(item, added_since="2026-03-15")
    assert search_filters.matches(item, added_until="2026-03-15")
    assert not search_filters.matches(item, added_since="2026-03-16")
    assert not search_filters.matches(item, added_until="2026-03-14")
    assert not search_filters.matches(_item(), added_since="2000-01-01")


def test_no_filters_matches_everything() -> None:
    assert search_filters.matches(_item())
