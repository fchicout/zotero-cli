import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

class ResourceTracker:
    """
    The Sentinel: Automatically tracks and purges remote Zotero resources.
    Ensures 'Zero-Leak' state even on test failures.
    """
    def __init__(self, run_cli):
        self.run_cli = run_cli
        self.created_collections = []

    def create_collection(self, name):
        """Creates a collection and registers it for tracking."""
        res = self.run_cli(["collection", "create", "--name", name])
        if res.returncode == 0:
            # We track by name/key. The CLI handles both.
            self.created_collections.append(name)
        return res

    def track(self, key_or_name):
        """Manually registers an existing resource for tracking."""
        if key_or_name not in self.created_collections:
            self.created_collections.append(key_or_name)

    def teardown(self):
        """Recursive cleanup of all tracked collections."""
        for col in reversed(self.created_collections):
            print(f"[QA_FORCE] Sentinel purging: {col}")
            # 1. Clean items first to prevent 'Unfiled' orphans
            self.run_cli(["collection", "clean", "--collection", col])
            # 2. Delete the collection itself
            res = self.run_cli(["collection", "delete", "--key", col, "--recursive"])
            if res.returncode != 0:
                print(f"[QA_FORCE] Cleanup failed for {col}: {res.stderr}")
        self.created_collections = []

def _run_cli_raw(args):
    """Internal helper to run CLI without fixture context."""
    cwd = Path.cwd()
    src_path = str(cwd / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = src_path
    return subprocess.run(
        [sys.executable, "-m", "zotero_cli.cli.main"] + args,
        capture_output=True,
        text=True,
        env=env,
    )

def pytest_sessionstart(session):
    """
    The Great Purge: Identifies and removes orphaned 'E2E_' collections.
    Ensures a defect-free starting state.
    """
    print("\n[QA_FORCE] Initiating orphan purge...")
    res = _run_cli_raw(["collection", "list", "--table"])
    if res.returncode == 0:
        # Regex to find E2E_ collections in the table output
        # Expecting rows like: │ E2E_Temp_123456 │ ABCDEFGH │ 0 │
        orphans = re.findall(r"│\s+(E2E_\S+)\s+│\s+([A-Z0-9]{8})\s+│", res.stdout)
        for name, key in orphans:
            print(f"[QA_FORCE] Purging orphan: {name} ({key})")
            _run_cli_raw(["collection", "clean", "--collection", key])
            _run_cli_raw(["collection", "delete", "--key", key, "--recursive"])

@pytest.fixture
def run_cli():
    """Fixture to run zotero-cli with correct PYTHONPATH."""
    def _run(args):
        return _run_cli_raw(args)
    return _run

@pytest.fixture
def sentinel(run_cli):
    """
    The Sentinel fixture: Manages resource lifecycle automatically.
    """
    tracker = ResourceTracker(run_cli)
    yield tracker
    tracker.teardown()

@pytest.fixture
def extract_keys():
    """Fixture to extract Zotero keys from text."""
    def _extract(text):
        return re.findall(r"\b([A-Z0-9]{8})\b", text)
    return _extract

@pytest.fixture
def timestamp():
    """Return a unique timestamp for collection naming."""
    return int(time.time())

@pytest.fixture
def temp_collection(sentinel, timestamp):
    """
    Legacy-compatible fixture using the Sentinel for safety.
    """
    col_name = f"E2E_Temp_{timestamp}"
    sentinel.create_collection(col_name)
    return col_name
