"""`.git-blame-ignore-revs` must list real commit ids (Issue #390)."""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _revs():
    lines = (REPO / ".git-blame-ignore-revs").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def _git(*args):
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(REPO), *args], capture_output=True, text=True
    )


def test_entries_are_full_commit_ids():
    revs = _revs()
    assert revs
    assert all(re.fullmatch(r"[0-9a-f]{40}", rev) for rev in revs)


def test_entries_exist_in_this_repository():
    """Needs full history: skipped in a source export and in shallow CI clones."""
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("not a git checkout")
    if _git("rev-parse", "--is-shallow-repository").stdout.strip() != "false":
        pytest.skip("shallow clone")
    for rev in _revs():
        assert _git("cat-file", "-e", f"{rev}^{{commit}}").returncode == 0, rev
