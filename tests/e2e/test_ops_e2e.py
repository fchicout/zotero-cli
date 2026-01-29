import re
import time

import pytest


@pytest.mark.e2e
def test_backup_restore_e2e(run_cli, tmp_path):
    """
    Real E2E: Verify that we can backup a collection and (mock) restore logic.
    Actually, we just verify the backup file is created.
    """
    ts = int(time.time())
    col_name = f"E2E_Backup_{ts}"
    backup_file = tmp_path / "backup.json"

    try:
        run_cli(["collection", "create", col_name])
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

    finally:
        # Cleanup
        run_cli(["collection", "delete", col_name, "--recursive"])


@pytest.mark.e2e
def test_shift_e2e(run_cli, tmp_path):
    """
    Real E2E: Verify shift detection.
    """
    ts = int(time.time())
    col_a = f"E2E_Shift_A_{ts}"
    col_b = f"E2E_Shift_B_{ts}"
    snap1 = tmp_path / "snap1.json"
    snap2 = tmp_path / "snap2.json"

    try:
        run_cli(["collection", "create", col_a])
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

        time.sleep(10)
        run_cli(["report", "snapshot", "--collection", col_a, "--output", str(snap1)])

        run_cli(["collection", "create", col_b])
        list_res = run_cli(["list", "items", "--collection", col_a])

        # Corrected Regex
        keys = re.findall(r"\b([A-Z0-9]{8})\b", list_res.stdout)
        item_keys = [k for k in keys if not k.isdigit()]
        if not item_keys:
            pytest.skip("No item key found")
        key = item_keys[0]

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

        time.sleep(10)
        run_cli(["report", "snapshot", "--collection", col_a, "--output", str(snap2)])

        shift_res = run_cli(["slr", "shift", "--old", str(snap1), "--new", str(snap2)])
        assert shift_res.returncode == 0
        assert key in shift_res.stdout

    finally:
        # Cleanup
        run_cli(["collection", "delete", col_a, "--recursive"])
        run_cli(["collection", "delete", col_b, "--recursive"])