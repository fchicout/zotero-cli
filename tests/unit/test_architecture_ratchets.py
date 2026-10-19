"""Ratchets that keep the architecture from drifting while it is being tidied (Issue #604).

Each baseline records what exists today and may only shrink: a new offender fails the
test, and fixing one means deleting or lowering its entry (a stale entry fails too).
Rules are checked on the AST, so lazy imports inside functions count.
"""

import ast
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List, Set, Tuple

import zotero_cli

SRC = Path(next(iter(zotero_cli.__path__)))
MAX_FILE_LINES = 1000
MAX_FUNCTION_LINES = 100

# Files over MAX_FILE_LINES, with their current length.
FILE_SIZE_BASELINE: Dict[str, int] = {}

# Functions over MAX_FUNCTION_LINES ("file::name"), with their current length.
FUNCTION_SIZE_BASELINE = {
    "cli/commands/import_cmd.py::register_args": 153,
    "cli/commands/init_cmd.py::execute": 150,
    "cli/commands/item_inspect.py::execute": 132,
    "cli/commands/report_cmd.py::register_args": 109,
    "cli/commands/report_cmd.py::_handle_attachments": 101,
    "cli/commands/search_cmd.py::execute": 127,
    "cli/commands/system_cmd.py::_handle_jobs": 102,
    "core/services/arxiv_query_parser.py::parse": 119,
    "core/services/resolvers/bdtd.py::resolve": 106,
    "infra/bdtd_api.py::_map_to_research_paper": 115,
    "infra/sqlite_repo.py::_fetch_items_with_filter": 111,
    "infra/zotero_api.py::create_item": 121,
}

# Commands that import a concrete infra adapter instead of asking GatewayFactory for it.
# "file: module" -> why it is still there.
CLI_INFRA_BASELINE = {
    "cli/commands/init_cmd.py: zotero_cli.infra.zotero_api": "checks credentials before any config exists",
    "cli/commands/item_cmd.py: zotero_cli.infra.sqlite_repo": "offline gateway for item inspect",
    "cli/commands/mcp_cmd.py: zotero_cli.infra.mcp_server": "lazy: the mcp extra is optional",
}

# Services, tools, strategies and gateways a command still builds itself instead of asking
# GatewayFactory ("file: class"). A ratchet: it only shrinks.
CLI_CONSTRUCTION_BASELINE = {
    "cli/commands/import_cmd.py: ArxivImportStrategy": "wraps the arXiv gateway for one call",
    "cli/commands/import_cmd.py: DoiImportStrategy": "wraps the metadata aggregator for one call",
    "cli/commands/import_cmd.py: SearchableProviderImportStrategy": "wraps the BDTD client",
}
_CONSTRUCTED_SUFFIXES = ("Service", "Tools", "Strategy", "Gateway")

# Modules in core that may use an HTTP library: the SSRF guard and the two clients that
# pin their address through it.
CORE_HTTP_ALLOWED = {
    "core/utils/url_safety.py",
    "core/services/network_gateway.py",
    "core/services/resolvers/openalex.py",
}
HTTP_LIBRARIES = {"requests", "httpx", "urllib3", "aiohttp"}

# Direct HTTP calls still made in each allowlisted module (see test_no_direct_http_calls).
# The allowlist is per file; this pins the number of calls per file so a new one needs a
# deliberate edit here.
DIRECT_HTTP_CALL_BASELINE = {
    "core/utils/url_safety.py": 1,
    "core/services/network_gateway.py": 1,
    "core/services/resolvers/openalex.py": 1,
    "infra/http_client.py": 3,
    "infra/pubmed_api.py": 1,
    "infra/base_api_client.py": 1,
}
_HTTP_CALLS = {
    "requests": {"get", "head", "post", "put", "patch", "delete", "request", "Session"},
    "httpx": {
        "get",
        "head",
        "post",
        "put",
        "patch",
        "delete",
        "request",
        "Client",
        "AsyncClient",
        "stream",
    },
}

# Broad `except Exception:` / bare `except:` handlers per file. They swallow programming
# errors along with the failures they mean to survive; a new one needs a deliberate edit.
BROAD_EXCEPT_BASELINE = {
    "api/dependencies.py": 2,
    "cli/commands/collection_cmd.py": 1,
    "cli/commands/init_cmd.py": 3,
    "cli/commands/system_cmd.py": 2,
    "cli/main.py": 1,
    "core/config.py": 2,
    "core/services/attachment_service.py": 4,
    "core/services/backup_service.py": 1,
    "core/services/diagnostics_service.py": 3,
    "core/services/enrichment_service.py": 2,
    "core/services/integrity_service.py": 1,
    "core/services/metadata_aggregator.py": 1,
    "core/services/pdf_finder_service.py": 1,
    "core/services/purge_service.py": 4,
    "core/services/resolvers/arxiv.py": 1,
    "core/services/resolvers/bdtd.py": 3,
    "core/services/resolvers/generic_scraper.py": 1,
    "core/services/resolvers/openalex.py": 1,
    "core/services/resolvers/semantic_scholar.py": 1,
    "core/services/resolvers/unpaywall.py": 1,
    "core/services/restore_service.py": 2,
    "core/services/selftest.py": 4,
    "core/services/storage_service.py": 3,
    "core/services/verify_service.py": 4,
    "infra/bdtd_api.py": 5,
    "infra/bibtex_lib.py": 2,
    "infra/core_api.py": 3,
    "infra/crossref_api.py": 1,
    "infra/dblp_api.py": 1,
    "infra/doaj_api.py": 3,
    "infra/eric_api.py": 1,
    "infra/hal_api.py": 1,
    "infra/ieee_csv_lib.py": 1,
    "infra/inspire_hep_api.py": 1,
    "infra/openalex_api.py": 2,
    "infra/pubmed_api.py": 3,
    "infra/repository_factory.py": 1,
    "infra/resolver_factory.py": 1,
    "infra/ris_lib.py": 2,
    "infra/semantic_scholar_api.py": 3,
    "infra/springer_csv_lib.py": 1,
    "infra/unpaywall_api.py": 1,
    "infra/zbmath_api.py": 1,
    "infra/zotero_api.py": 18,
}

# `sys.exit(...)` calls in commands, per file. Commands raise ZoteroCliError (see
# core/exceptions.py) and main() turns it into the exit code.
SYS_EXIT_BASELINE = {
    "cli/commands/collection_cmd.py": 8,
    "cli/commands/init_cmd.py": 1,
    "cli/commands/item_cmd.py": 11,
    "cli/commands/report_cmd.py": 2,
    "cli/commands/serve_cmd.py": 1,
    "cli/commands/system_cmd.py": 2,
}

# Import cycles that exist today (module sets).
CYCLE_BASELINE = [
    {"zotero_cli.core.config", "zotero_cli.core.logging_config"},
]


def _files(layer: str = "") -> Iterator[Path]:
    yield from sorted((SRC / layer).rglob("*.py"))


def _rel(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_modules(tree: ast.AST) -> Iterator[Tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name


# ---- size ------------------------------------------------------------------------------


def _file_sizes() -> Dict[str, int]:
    sizes = {_rel(p): len(p.read_text(encoding="utf-8").splitlines()) for p in _files()}
    return {f: n for f, n in sizes.items() if n > MAX_FILE_LINES}


def _function_sizes() -> Dict[str, int]:
    found: Dict[str, int] = {}
    for path in _files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = (node.end_lineno or node.lineno) - node.lineno + 1
                if length > MAX_FUNCTION_LINES:
                    key = f"{_rel(path)}::{node.name}"
                    found[key] = max(found.get(key, 0), length)
    return found


def test_no_new_oversized_files():
    grew = {f: n for f, n in _file_sizes().items() if n > FILE_SIZE_BASELINE.get(f, 0)}
    assert grew == {}, f"split the module instead of growing it past {MAX_FILE_LINES} lines"


def test_file_size_baseline_is_lowered_as_files_are_split():
    sizes = _file_sizes()
    stale = {f: n for f, n in FILE_SIZE_BASELINE.items() if sizes.get(f, 0) < n}
    assert stale == {}, "lower or delete these in FILE_SIZE_BASELINE (it only shrinks)"


def test_no_new_oversized_functions():
    grew = {f: n for f, n in _function_sizes().items() if n > FUNCTION_SIZE_BASELINE.get(f, 0)}
    assert grew == {}, (
        f"extract helpers instead of growing a function past {MAX_FUNCTION_LINES} lines"
    )


def test_function_size_baseline_is_lowered_as_functions_are_split():
    sizes = _function_sizes()
    stale = {f: n for f, n in FUNCTION_SIZE_BASELINE.items() if sizes.get(f, 0) < n}
    assert stale == {}, "lower or delete these in FUNCTION_SIZE_BASELINE (it only shrinks)"


# ---- layers ----------------------------------------------------------------------------


def test_api_does_not_import_cli():
    found = [
        f"{_rel(p)}:{line} imports {mod}"
        for p in _files("api")
        for line, mod in _imported_modules(_tree(p))
        if mod == "zotero_cli.cli" or mod.startswith("zotero_cli.cli.")
    ]
    assert found == []


def _cli_infra_imports() -> Set[str]:
    found = set()
    for path in _files("cli"):
        for _, mod in _imported_modules(_tree(path)):
            if mod.startswith("zotero_cli.infra.") and "factory" not in mod:
                found.add(f"{_rel(path)}: {mod}")
    return found


def test_cli_gets_infra_adapters_from_the_factory():
    new = _cli_infra_imports() - set(CLI_INFRA_BASELINE)
    assert new == set(), "ask GatewayFactory (infra/factory.py) for it instead of importing infra"


def test_cli_infra_baseline_is_lowered_as_commands_move_to_the_factory():
    stale = set(CLI_INFRA_BASELINE) - _cli_infra_imports()
    assert stale == set(), "delete these from CLI_INFRA_BASELINE (it only shrinks)"


def _cli_constructions() -> Set[str]:
    found = set()
    for path in _files("cli"):
        for node in ast.walk(_tree(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id[:1].isupper()
                and node.func.id.endswith(_CONSTRUCTED_SUFFIXES)
            ):
                found.add(f"{_rel(path)}: {node.func.id}")
    return found


def test_cli_does_not_construct_services_itself():
    new = _cli_constructions() - set(CLI_CONSTRUCTION_BASELINE)
    assert new == set(), (
        "add a getter to ServiceFactory/MetadataClientFactory and use GatewayFactory"
    )


def test_cli_construction_baseline_is_lowered_as_commands_move_to_the_factory():
    stale = set(CLI_CONSTRUCTION_BASELINE) - _cli_constructions()
    assert stale == set(), "delete these from CLI_CONSTRUCTION_BASELINE (it only shrinks)"


# ---- HTTP ------------------------------------------------------------------------------


def test_core_uses_http_libraries_only_in_the_ssrf_guarded_modules():
    found = [
        f"{_rel(p)}:{line} imports {mod}"
        for p in _files("core")
        if _rel(p) not in CORE_HTTP_ALLOWED
        for line, mod in _imported_modules(_tree(p))
        if mod.split(".")[0] in HTTP_LIBRARIES or mod.startswith("urllib.request")
    ]
    assert found == [], "core reaches the network through url_safety or NetworkGateway"


def test_only_the_arxiv_gateway_imports_arxiv_or_urllib_request():
    found = [
        f"{_rel(p)}:{line} imports {mod}"
        for p in _files()
        if _rel(p) != "infra/arxiv_lib.py"
        for line, mod in _imported_modules(_tree(p))
        if mod.split(".")[0] == "arxiv" or mod.startswith("urllib.request")
    ]
    assert found == [], "arxiv does its own HTTP, retries and pacing: keep it behind arxiv_lib"


def _http_names(tree: ast.AST) -> Tuple[Dict[str, str], Dict[str, str]]:
    """(local name -> library, local name -> 'library.function') for requests/httpx."""
    modules: Dict[str, str] = {}
    functions: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _HTTP_CALLS:
                    modules[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in _HTTP_CALLS and node.level == 0:
            for alias in node.names:
                if alias.name in _HTTP_CALLS[node.module]:
                    functions[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return modules, functions


def _direct_http_calls(path: Path) -> int:
    """Calls like requests.get(...), r.get(...) after `import requests as r`, or get(...)
    after `from requests import get`."""
    tree = _tree(path)
    modules, functions = _http_names(tree)
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in functions:
            count += 1
        elif (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id in modules
            and func.attr in _HTTP_CALLS[modules[func.value.id]]
        ):
            count += 1
    return count


def _http_call_counts() -> Dict[str, int]:
    counts = {_rel(p): _direct_http_calls(p) for p in _files()}
    return {f: n for f, n in counts.items() if n}


def test_direct_http_calls_are_pinned_per_file():
    grew = {f: n for f, n in _http_call_counts().items() if n > DIRECT_HTTP_CALL_BASELINE.get(f, 0)}
    assert grew == {}, (
        "route the call through url_safety or the file's own client (even via an alias)"
    )


def test_direct_http_call_baseline_is_lowered_as_calls_are_routed():
    counts = _http_call_counts()
    stale = {f: n for f, n in DIRECT_HTTP_CALL_BASELINE.items() if counts.get(f, 0) < n}
    assert stale == {}, "lower or delete these in DIRECT_HTTP_CALL_BASELINE (it only shrinks)"


def test_every_metadata_client_builds_on_the_shared_base():
    outside = []
    for path in _files("infra"):
        if not path.name.endswith("_api.py") or path.name == "zotero_api.py":
            continue  # the Zotero client goes through ZoteroHttpClient
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ClassDef) and node.name.endswith("APIClient"):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                if "BaseAPIClient" not in bases:
                    outside.append(f"{_rel(path)}: {node.name}")
    assert outside == [], "subclass BaseAPIClient (infra/base_api_client.py) for pacing and retries"


def _count(rel_prefix: str, matches) -> Dict[str, int]:
    counts: Counter = Counter()
    for path in _files():
        if _rel(path).startswith(rel_prefix):
            counts[_rel(path)] += sum(1 for node in ast.walk(_tree(path)) if matches(node))
    return {f: n for f, n in counts.items() if n}


def _is_broad_except(node: ast.AST) -> bool:
    return isinstance(node, ast.ExceptHandler) and (
        node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
    )


def _is_sys_exit(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "exit"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "sys"
    )


def test_no_new_broad_except_handlers():
    grew = {
        f: n for f, n in _count("", _is_broad_except).items() if n > BROAD_EXCEPT_BASELINE.get(f, 0)
    }
    assert grew == {}, "catch the specific errors you expect (it only goes down)"


def test_broad_except_baseline_is_lowered_as_handlers_are_narrowed():
    counts = _count("", _is_broad_except)
    stale = {f: n for f, n in BROAD_EXCEPT_BASELINE.items() if counts.get(f, 0) < n}
    assert stale == {}, "lower or delete these in BROAD_EXCEPT_BASELINE (it only shrinks)"


def test_no_new_sys_exit_in_commands():
    grew = {
        f: n
        for f, n in _count("cli/commands/", _is_sys_exit).items()
        if n > SYS_EXIT_BASELINE.get(f, 0)
    }
    assert grew == {}, "raise a ZoteroCliError subclass; main() maps it to the exit code"


def test_sys_exit_baseline_is_lowered_as_commands_raise_errors():
    counts = _count("cli/commands/", _is_sys_exit)
    stale = {f: n for f, n in SYS_EXIT_BASELINE.items() if counts.get(f, 0) < n}
    assert stale == {}, "lower or delete these in SYS_EXIT_BASELINE (it only shrinks)"


# ---- imports ---------------------------------------------------------------------------


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(SRC.parent).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _import_graph() -> Dict[str, Set[str]]:
    modules = {_module_name(p) for p in _files()}
    graph: Dict[str, Set[str]] = {m: set() for m in modules}
    for path in _files():
        here = _module_name(path)
        for node in ast.walk(_tree(path)):
            targets: List[str] = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                targets = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for target in targets:
                # A package import (zotero_cli.core) only runs its __init__, which the
                # submodule edges already cover; keep edges between real modules.
                if target in modules and target != here and not _is_package(target):
                    graph[here].add(target)
    return graph


def _is_package(module: str) -> bool:
    return (SRC.parent.joinpath(*module.split("."), "__init__.py")).exists()


def _cycles(graph: Dict[str, Set[str]]) -> List[Set[str]]:
    """Strongly connected components with more than one module (Tarjan)."""
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    stack: List[str] = []
    on_stack: Set[str] = set()
    found: List[Set[str]] = []
    counter = [0]

    def visit(start: str) -> None:
        work = [(start, iter(sorted(graph[start])))]
        index[start] = low[start] = counter[0]
        counter[0] += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(graph[child]))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = set()
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.add(member)
                    if member == node:
                        break
                if len(component) > 1:
                    found.append(component)

    for module in sorted(graph):
        if module not in index:
            visit(module)
    return found


def test_no_new_import_cycles():
    new = [c for c in _cycles(_import_graph()) if c not in CYCLE_BASELINE]
    assert new == [], f"break the cycle (move the shared part into a leaf module): {new}"


def test_cycle_baseline_is_lowered_as_cycles_are_broken():
    current = _cycles(_import_graph())
    stale = [c for c in CYCLE_BASELINE if c not in current]
    assert stale == [], "delete these from CYCLE_BASELINE (it only shrinks)"


def test_importing_every_module_has_no_side_effects(tmp_path: Path):
    """Importing the package must not touch the user's config or home directory."""
    home = tmp_path / "home"
    home.mkdir()
    script = (
        "import importlib, pkgutil, zotero_cli\n"
        "for m in pkgutil.walk_packages(zotero_cli.__path__, 'zotero_cli.'):\n"
        "    importlib.import_module(m.name)\n"
    )
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", script], env=env, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert list(home.iterdir()) == [], "importing a module wrote into the home directory"


# ---- stringly-typed contracts ----------------------------------------------------------


def _search_sort_choices() -> List[str]:
    for node in ast.walk(_tree(SRC / "cli" / "commands" / "search_cmd.py")):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "--sort"
        ):
            for keyword in node.keywords:
                if keyword.arg == "choices":
                    return list(ast.literal_eval(keyword.value))
    raise AssertionError("search --sort choices not found")


def test_sort_fields_agree_across_cli_mcp_and_sqlite():
    from zotero_cli.core.services.agent_tools import SORT_FIELDS
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    assert list(SORT_FIELDS) == _search_sort_choices() == list(SqliteZoteroGateway.SORT_FIELDS)


def test_default_hydrate_fields_are_hydratable():
    from zotero_cli.core.services.enrichment_service import DEFAULT_FIELDS, HYDRATABLE_FIELDS

    assert set(DEFAULT_FIELDS) <= set(HYDRATABLE_FIELDS)
    assert Counter(HYDRATABLE_FIELDS).most_common(1)[0][1] == 1, "duplicate hydratable field"
