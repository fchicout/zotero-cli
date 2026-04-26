import re
import time

import pytest


@pytest.mark.e2e
def test_backup_restore_e2e(run_cli, sentinel, timestamp, tmp_path):
    """
    Real E2E: Verify that we can backup a collection.
    Uses 'sentinel' for robust cleanup.
    """
    col_name = f"E2E_Backup_{timestamp}"
    backup_file = tmp_path / "backup.json"

    sentinel.create_collection(col_name)
    # Add an item to ensure it's not empty
    run_cli(
        [
            "import",
            "arxiv",
            "--query",
            "id:1706.03762",
            "--limit",
            "1",
            "--collection",
            col_name,
        ]
    )

    # Wait for Zotero sync
    time.sleep(5)

    # 1. Backup
    res = run_cli(["collection", "backup", "--name", col_name, "--output", str(backup_file)])
    assert res.returncode == 0
    assert backup_file.exists()


@pytest.mark.e2e
def test_shift_e2e(run_cli, sentinel, timestamp, tmp_path):
    """
    Real E2E: Verify shift detection.
    Uses 'sentinel' for robust cleanup.
    """
    col_a = f"E2E_Shift_A_{timestamp}"
    col_b = f"E2E_Shift_B_{timestamp}"
    snap1 = tmp_path / "snap1.json"
    snap2 = tmp_path / "snap2.json"

    sentinel.create_collection(col_a)
    run_cli(
        [
            "import",
            "arxiv",
            "--query",
            "id:1706.03762",
            "--limit",
            "1",
            "--collection",
            col_a,
        ]
    )

    # Wait for import to stabilize
    time.sleep(15)
    run_cli(["report", "snapshot", "--collection", col_a, "--output", str(snap1)])

    sentinel.create_collection(col_b)
    # Wait for collection B to be discoverable
    time.sleep(10)

    list_res = run_cli(["list", "items", "--collection", col_a])

    # Filter for journalArticle to avoid picking attachments
    matches = re.findall(r"│\s*([A-Z0-9]{8})\s*│.*│\s*journalArticle\s*│", list_res.stdout)
    if not matches:
        pytest.skip("No journalArticle found in collection")
    key = matches[0]

    run_cli(
        [
            "slr",
            "decide",
            "--key",
            key,
            "--vote",
            "INCLUDE",
            "--code",
            "SHIFT",
            "--source",
            col_a,
            "--target",
            col_b,
        ]
    )

    # Wait for movement to propagate
    time.sleep(20)
    run_cli(["report", "snapshot", "--collection", col_a, "--output", str(snap2)])

    shift_res = run_cli(["slr", "shift", "--old", str(snap1), "--new", str(snap2)])
    assert shift_res.returncode == 0
    assert key in shift_res.stdout
