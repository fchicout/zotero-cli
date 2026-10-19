"""A ceiling on spec-less `MagicMock()` / `Mock()` / `AsyncMock()` in tests/unit (Issues #389, #604).

A bare mock (even one given only a `return_value` or `side_effect`) accepts any attribute and any call, so a renamed or re-signed method in a
real interface goes unnoticed. New tests should take the autospec fixtures from
tests/unit/conftest.py (`mock_gateway`, `mock_item_repo`, ...), or `create_autospec` /
`Mock(spec=...)`, or give the mock a `spec`. The count may only go down: when you
replace some, lower the ceiling.
"""

import ast
from pathlib import Path

UNIT = Path(__file__).resolve().parent
BARE_MOCK_CEILING = 554
THIS_FILE = Path(__file__).resolve()


def _bare_mocks() -> int:
    count = 0
    for path in UNIT.rglob("*.py"):
        if path.resolve() == THIS_FILE:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or node.args:
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in ("MagicMock", "Mock", "AsyncMock") and not any(
                keyword.arg in ("spec", "spec_set", "autospec") for keyword in node.keywords
            ):
                count += 1
    return count


def test_no_new_bare_mocks() -> None:
    assert _bare_mocks() <= BARE_MOCK_CEILING, (
        "use the autospec fixtures in tests/unit/conftest.py or give the mock a spec"
    )


def test_the_ceiling_is_lowered_as_bare_mocks_are_replaced() -> None:
    assert _bare_mocks() == BARE_MOCK_CEILING, "lower BARE_MOCK_CEILING to the new count"
