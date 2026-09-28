"""Issue #368: a CLI handler that prints an error and then `return`s exits 0,
so scripts can't tell it failed. Handlers raise a typed error instead
(core/exceptions.py), which main() turns into one stderr line and an exit
code (docs/EXIT_CODES.md)."""

import ast
import re
from pathlib import Path

CLI = Path(__file__).resolve().parents[2] / "src" / "zotero_cli" / "cli"
ERROR_TEXT = re.compile(r"(error|not found|must specify|required)", re.I)
# Notices that mention these words but aren't failures.
ALLOWED = re.compile(r"(Preview only|DRY RUN)", re.I)


def _silent_error_returns():
    found = []
    for path in sorted(CLI.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, None)
                if not isinstance(block, list):
                    continue
                for first, second in zip(block, block[1:]):
                    if not isinstance(second, ast.Return) or second.value is not None:
                        continue
                    if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)):
                        continue
                    func = first.value.func
                    if getattr(func, "attr", getattr(func, "id", "")) != "print":
                        continue
                    text = ast.get_source_segment(src, first) or ""
                    if ERROR_TEXT.search(text) and not ALLOWED.search(text):
                        found.append(f"{path.relative_to(CLI)}:{first.lineno}")
    return found


def test_cli_errors_raise_instead_of_printing_and_returning():
    silent = _silent_error_returns()
    assert not silent, (
        "These print an error and return (exit 0); raise NotFound/UsageError/"
        f"ZoteroCliError instead: {silent}"
    )
