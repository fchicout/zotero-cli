"""Layering rules for the hexagonal architecture (Issue #393).

cli -> core, infra; infra -> core; core -> neither. Domain code reports through
return values and `logging`, not `print`. Rules are checked on the AST so lazy
imports inside functions count too.
"""

import ast
from collections import Counter
from pathlib import Path
from typing import Iterator, List, Tuple

SRC = Path(__file__).resolve().parents[2] / "src" / "zotero_cli"

# `print()` calls still in the domain/adapter layers, per file. A ratchet: it may
# only go down. Fixing a file means lowering its number (or deleting the line);
# a new print anywhere fails the test.
PRINT_BASELINE = {
    "api/main.py": 1,
    "core/config.py": 3,
    "core/logging_config.py": 1,
    "core/services/attachment_service.py": 3,
    "core/services/audit_service.py": 1,
    "core/services/graph_service.py": 1,
    "core/services/import_service.py": 2,
    "core/services/metadata_aggregator.py": 1,
    "core/services/report_service.py": 2,
    "core/services/slr/csv_inbound.py": 1,
    "core/services/slr/integrity.py": 1,
    "core/services/snapshot_service.py": 4,
    "infra/bibtex_lib.py": 1,
    "infra/http_client.py": 1,
    "infra/opener.py": 3,
    "infra/resolver_factory.py": 1,
    "infra/ris_lib.py": 1,
    "infra/sqlite_repo.py": 1,
}

# core may use rich only in the terminal-safety helpers every layer shares.
RICH_IN_CORE_ALLOWED = {"core/utils/terminal_safety.py"}


def _python_files(layer: str) -> Iterator[Path]:
    yield from sorted((SRC / layer).rglob("*.py"))


def _imports(path: Path) -> Iterator[Tuple[int, str]]:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name


def _violations(layer: str, forbidden: Tuple[str, ...]) -> List[str]:
    found = []
    for path in _python_files(layer):
        rel = path.relative_to(SRC).as_posix()
        for line, module in _imports(path):
            if any(module == f or module.startswith(f + ".") for f in forbidden):
                found.append(f"{rel}:{line} imports {module}")
    return found


def test_core_does_not_import_infra_or_cli():
    assert _violations("core", ("zotero_cli.infra", "zotero_cli.cli")) == []


def test_infra_does_not_import_cli():
    assert _violations("infra", ("zotero_cli.cli",)) == []


def test_core_does_not_render_with_rich():
    found = [
        v for v in _violations("core", ("rich",)) if v.split(":")[0] not in RICH_IN_CORE_ALLOWED
    ]
    assert found == []


def _print_counts() -> Counter:
    counts: Counter = Counter()
    for layer in ("core", "infra", "api"):
        for path in _python_files(layer):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                ):
                    counts[path.relative_to(SRC).as_posix()] += 1
    return counts


def test_no_new_print_in_core_infra_or_api():
    counts = _print_counts()
    more = {f: n for f, n in counts.items() if n > PRINT_BASELINE.get(f, 0)}
    assert more == {}, "use logging (or return the message to the CLI) instead of print()"


def test_print_baseline_is_lowered_as_prints_are_removed():
    counts = _print_counts()
    stale = {f: n for f, n in PRINT_BASELINE.items() if counts.get(f, 0) < n}
    assert stale == {}, "lower PRINT_BASELINE to the new counts (it only goes down)"
