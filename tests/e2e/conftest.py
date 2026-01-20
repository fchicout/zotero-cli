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
