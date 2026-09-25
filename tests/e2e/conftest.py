import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

# --- Opt-in guard (Issue #400) ---
#
# These tests create and delete collections and items in whichever Zotero
# library is configured, and the session start purges every `E2E_*`
# collection there. They only run when a human asks for them, against a
# library named explicitly:
#
#   ZOTERO_CLI_E2E=1 ZOTERO_CLI_E2E_LIBRARY_ID=<sandbox library id> \
#       uv run pytest tests/e2e
#
# The id must match the library the CLI resolves from the current config,
# so a stale shell variable can't aim the suite at a real library.

E2E_DIR = Path(__file__).parent


def e2e_skip_reason() -> str | None:
    """None if the e2e suite may run, else why it may not."""
    if os.environ.get("ZOTERO_CLI_E2E") != "1":
        return "e2e tests write to a real Zotero library; set ZOTERO_CLI_E2E=1 to opt in"
    wanted = os.environ.get("ZOTERO_CLI_E2E_LIBRARY_ID", "").strip()
    if not wanted:
        return "set ZOTERO_CLI_E2E_LIBRARY_ID to the sandbox library the suite may modify"
    try:
        from zotero_cli.core.config import get_config

        configured, _ = get_config().resolve_library_target(False, False)
    except Exception as exc:
        return f"could not resolve the configured library: {exc}"
    if str(configured) != wanted:
        return (
            f"the configured library ({configured}) is not ZOTERO_CLI_E2E_LIBRARY_ID "
            f"({wanted}); refusing to modify it"
        )
    return None


def pytest_collection_modifyitems(config, items):
    reason = e2e_skip_reason()
    if reason is None:
        return
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if E2E_DIR in Path(str(item.fspath)).parents:
            item.add_marker(skip)


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
            # Deletes the collection tree and the items filed only in it.
            # (`collection clean` no longer deletes items, only unfiles
            # them: running it first would leave orphans behind.)
            res = self.run_cli(
                ["collection", "delete", "--key", col, "--recursive", "--execute", "--yes"]
            )
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
    if e2e_skip_reason() is not None:
        return
    print("\n[QA_FORCE] Initiating orphan purge...")
    res = _run_cli_raw(["collection", "list", "--table"])
    if res.returncode == 0:
        # Regex to find E2E_ collections in the table output
        # Expecting rows like: │ E2E_Temp_123456 │ ABCDEFGH │ 0 │
        orphans = re.findall(r"│\s+(E2E_\S+)\s+│\s+([A-Z0-9]{8})\s+│", res.stdout)
        for name, key in orphans:
            print(f"[QA_FORCE] Purging orphan: {name} ({key})")
            _run_cli_raw(
                ["collection", "delete", "--key", key, "--recursive", "--execute", "--yes"]
            )


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
