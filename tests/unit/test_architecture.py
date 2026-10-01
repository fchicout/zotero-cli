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
    "core/config.py": 3,
    "core/logging_config.py": 1,
}

# Left on purpose: these run before the CLI installs its sink or sets up logging
# (config loading, logging bootstrap), so a message can only go straight to stderr.
# core/config.py: 3, core/logging_config.py: 1.


# Services that still take the whole `ZoteroGateway` instead of the narrow repository
# interfaces (ItemRepository, CollectionRepository, NoteRepository, ...). A ratchet like
# PRINT_BASELINE: no new service may join, and narrowing one means deleting its line.
# Most need two or more repositories or a gateway-only method (search_items,
# verify_credentials, count_items), so narrowing them changes constructors; do it as
# each is touched.
GATEWAY_BASELINE = {
    "core/services/backup_service.py",
    "core/services/children_index.py",
    "core/services/diagnostics_service.py",
    "core/services/duplicate_service.py",
    "core/services/purge_service.py",
    "core/services/rag_service.py",
    "core/services/report_service.py",
    "core/services/restore_service.py",
    "core/services/sdb/sdb_service.py",
    "core/services/slr/csv_inbound.py",
    "core/services/slr/integrity.py",
    "core/services/slr/orchestrator.py",
    "core/services/slr/status_service.py",
    "core/services/storage_service.py",
    "core/services/transfer_service.py",
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


def _services_using_the_full_gateway() -> set:
    users = set()
    for path in _python_files("core/services"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Name) and node.id == "ZoteroGateway") or (
                isinstance(node, ast.alias) and node.name == "ZoteroGateway"
            ):
                users.add(path.relative_to(SRC).as_posix())
    return users


def test_no_new_service_takes_the_full_gateway():
    new = _services_using_the_full_gateway() - GATEWAY_BASELINE
    assert new == set(), "take the narrow repository interfaces from core/interfaces.py instead"


def test_gateway_baseline_is_lowered_as_services_are_narrowed():
    stale = GATEWAY_BASELINE - _services_using_the_full_gateway()
    assert stale == set(), "delete these from GATEWAY_BASELINE (it only shrinks)"
