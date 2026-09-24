"""slr list --xlsx: collaborator-controlled text must be stored as literal
strings. openpyxl isn't a dependency (tests/conftest.py replaces it with a
MagicMock), so this uses a stand-in with openpyxl's behaviour: `append`
marks any string starting with "=" as a formula (data_type "f")."""

import sys
import types

from zotero_cli.cli.commands.slr.list_cmd import ListCommand


class _Cell:
    def __init__(self, value):
        self.value = value
        self.data_type = "f" if isinstance(value, str) and value.startswith("=") else "s"


class _Sheet:
    def __init__(self):
        self.rows = []
        self.title = ""

    def append(self, values):
        self.rows.append([_Cell(v) for v in values])

    @property
    def max_row(self):
        return len(self.rows)

    def __getitem__(self, row_number):
        return self.rows[row_number - 1]


class _Workbook:
    last: "_Workbook | None" = None

    def __init__(self):
        self.active = _Sheet()
        _Workbook.last = self

    def save(self, filename):
        pass


def test_xlsx_export_stores_formula_like_text_as_literal_strings(monkeypatch):
    monkeypatch.setitem(sys.modules, "openpyxl", types.SimpleNamespace(Workbook=_Workbook))

    class Item:
        item_key = "K1"
        title = '=HYPERLINK("http://evil.example","click")'
        source_collection = "Source"
        reason = "=1+1"

    ListCommand._export_xlsx([Item()], "out.xlsx")  # type: ignore[list-item]

    assert _Workbook.last is not None
    data_row = _Workbook.last.active[2]
    assert data_row[1].value == '=HYPERLINK("http://evil.example","click")'
    assert all(cell.data_type == "s" for cell in data_row)
