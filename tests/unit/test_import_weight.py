"""Starting zotero-cli doesn't import stacks the command may not use
(Issue #433: `--help` imported 702 modules; requests, httpx, bibtexparser
and uvicorn alone cost ~145 ms on every invocation)."""

import subprocess
import sys

HEAVY = ("requests", "httpx", "httpcore", "bibtexparser", "uvicorn", "tenacity", "asyncio")


def test_building_the_cli_imports_no_heavy_packages():
    code = (
        "import sys; import zotero_cli.cli.main as m; m.build_parser(); "
        f"print(','.join(p for p in {HEAVY!r} if p in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=True
    )
    assert result.stdout.strip() == "", f"imported at startup: {result.stdout.strip()}"
