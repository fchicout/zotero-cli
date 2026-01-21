import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture
def run_cli():
    """Fixture to run zotero-cli with correct PYTHONPATH."""

    def _run(args):
        cwd = Path.cwd()
        src_path = str(cwd / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = src_path

        # Ensure we use the same interpreter as pytest
        result = subprocess.run(
            [sys.executable, "-m", "zotero_cli.cli.main"] + args,
            capture_output=True,
            text=True,
            env=env,
        )
        return result

    return _run


@pytest.fixture
def extract_keys():
    """Fixture to extract Zotero keys from text."""

    def _extract(text):
        # Matches 8-character uppercase alphanumeric strings
        # Specifically inside Rich table borders or as word boundaries
        return re.findall(r"\b([A-Z0-9]{8})\b", text)

    return _extract


@pytest.fixture
def timestamp():
    """Return a unique timestamp for collection naming."""
    return int(time.time())


@pytest.fixture
def temp_collection(run_cli, timestamp):
    """
    Yields a temporary collection name.
    Ensures rigorous teardown (Clean Items -> Delete Collection) to prevent
    'Unfiled' orphans in the Zotero Library.
    """
    col_name = f"E2E_Temp_{timestamp}"

    # 1. Create
    run_cli(["collection", "create", col_name])

    yield col_name

    # 2. Teardown: Clean then Delete
    # Clean deletes the actual items, preventing orphans.
    print(f"\n[Teardown] Cleaning collection: {col_name}")
    clean_res = run_cli(["collection", "clean", "--collection", col_name])
    if clean_res.returncode != 0:
        print(f"Warning: Clean failed: {clean_res.stderr}")

    print(f"[Teardown] Deleting collection: {col_name}")
    del_res = run_cli(["collection", "delete", col_name, "--recursive"])
    if del_res.returncode != 0:
        print(f"Warning: Delete failed: {del_res.stderr}")
