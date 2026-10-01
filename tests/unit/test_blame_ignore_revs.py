"""`.git-blame-ignore-revs` must list real commit ids (Issue #390)."""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _revs():
    lines = (REPO / ".git-blame-ignore-revs").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def test_entries_are_full_commit_ids():
    revs = _revs()
    assert revs
    assert all(re.fullmatch(r"[0-9a-f]{40}", rev) for rev in revs)


def test_entries_exist_in_this_repository():
    """Skipped in a source export without history."""
    probe = subprocess.run(  # noqa: S603
        ["git", "-C", str(REPO), "rev-parse", "--git-dir"], capture_output=True, text=True
    )
    if probe.returncode != 0:
        return
    for rev in _revs():
        known = subprocess.run(  # noqa: S603
            ["git", "-C", str(REPO), "cat-file", "-e", f"{rev}^{{commit}}"], capture_output=True
        )
        assert known.returncode == 0, rev
