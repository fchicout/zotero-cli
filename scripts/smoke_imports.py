"""Imports every zotero_cli module and exits non-zero if any fails.

Run it in an environment with only the runtime dependencies installed
(`uv sync --locked`, no extras). It catches a module-level import of
something that's only a dev or optional dependency, which `--help` alone
misses when the import sits behind a lazily-imported module (Issue #333).
"""

import importlib
import sys
from pathlib import Path

import zotero_cli


def module_names() -> list[str]:
    # Walk the files rather than using pkgutil.walk_packages, which skips
    # folders without an __init__.py (core/utils, cli/presenters, ...) and
    # never descends into a package whose own import failed.
    root = Path(next(iter(zotero_cli.__path__)))
    names = []
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root.parent).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names.append(".".join(parts))
    return names


def main() -> int:
    names = module_names()
    failures = []
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001 - report every failure, not just the first
            failures.append(f"{name}: {type(e).__name__}: {e}")
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"Imported {len(names) - len(failures)}/{len(names)} modules.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
