"""Guards the SSRF protection from regressions: a new module-level
`requests.get(...)`/`httpx.AsyncClient(...)` etc. bypasses url_safety's
URL validation and address pinning. URLs from item data or third-party
API responses must go through `safe_get`/`safe_head`/`safe_get_text`/
`safe_async_get` (with a `pin_public_ips` client) or NetworkGateway.

Modules on the allowlist only ever talk to fixed, hardcoded API hosts, or
are the SSRF guard itself."""

import ast
from pathlib import Path

import zotero_cli

SRC = Path(next(iter(zotero_cli.__path__)))

_DIRECT_CALLS = {
    "requests": {"get", "head", "post", "put", "patch", "delete", "request", "Session"},
    "httpx": {"get", "head", "post", "put", "patch", "delete", "request", "Client", "AsyncClient", "stream"},
}

ALLOWLIST = {
    # The SSRF guard itself.
    "core/utils/url_safety.py",
    # Pins its client with pin_public_ips and validates every hop.
    "core/services/network_gateway.py",
    "core/services/resolvers/openalex.py",
    # Fixed API hosts (Zotero, NCBI, the shared metadata-client base).
    "infra/http_client.py",
    "infra/pubmed_api.py",
    "infra/base_api_client.py",
}


def _direct_calls(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.attr in _DIRECT_CALLS.get(node.func.value.id, set())
        ):
            yield f"{node.func.value.id}.{node.func.attr} (line {node.lineno})"


def test_no_unguarded_http_calls_outside_the_allowlist():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel in ALLOWLIST:
            continue
        offenders += [f"{rel}: {call}" for call in _direct_calls(path)]
    assert not offenders, (
        "Direct HTTP calls bypass the SSRF guard - use url_safety's safe_* helpers "
        "or NetworkGateway, or allowlist a fixed-host API client:\n" + "\n".join(offenders)
    )


def test_allowlist_has_no_stale_entries():
    for rel in ALLOWLIST:
        assert (SRC / rel).exists(), f"{rel} no longer exists - drop it from ALLOWLIST"
