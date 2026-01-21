import re
import time

import pytest


@pytest.mark.e2e
def test_prune_e2e(run_cli):
    """
    Real E2E: Verify zotero-cli slr prune removes intersection.
    """
    ts = int(time.time())
    col_inc = f"E2E_Prune_Inc_{ts}"
    col_exc = f"E2E_Prune_Exc_{ts}"

    try:
        # 1. Setup Collections
        run_cli(["collection", "create", col_inc])
        run_cli(["collection", "create", col_exc])

        # 2. Import same paper to BOTH
        import_cmd = ["import", "arxiv", "--query", "id:1706.03762", "--limit", "1"]
        run_cli(import_cmd + ["--collection", col_inc])
        run_cli(import_cmd + ["--collection", col_exc])

        # 3. Verify item is in both (Wait for sync)
        time.sleep(5)
        res_exc = run_cli(["list", "items", "--collection", col_exc])
        assert "Attention" in res_exc.stdout

        # 4. Action: Prune
        prune_res = run_cli(["slr", "prune", "--included", col_inc, "--excluded", col_exc])
        print(f"PRUNE STDOUT: {prune_res.stdout}")
        print(f"PRUNE STDERR: {prune_res.stderr}")
        assert prune_res.returncode == 0
        assert "Pruned" in prune_res.stdout
        assert "items" in prune_res.stdout

        # 5. Verify item GONE (Wait longer for index update)
        time.sleep(5)
        res_after = run_cli(["list", "items", "--collection", col_exc])
        assert "Attention" not in res_after.stdout

    finally:
        # Rigorous Cleanup
        for col in [col_inc, col_exc]:
            run_cli(["collection", "clean", "--collection", col])
            run_cli(["collection", "delete", col, "--recursive"])


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

        time.sleep(5)
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

        time.sleep(5)
        run_cli(["report", "snapshot", "--collection", col_a, "--output", str(snap2)])

        shift_res = run_cli(["slr", "shift", "--old", str(snap1), "--new", str(snap2)])
        assert shift_res.returncode == 0
        assert key in shift_res.stdout

    finally:
        # Rigorous Cleanup
        for col in [col_a, col_b]:
            run_cli(["collection", "clean", "--collection", col])
            run_cli(["collection", "delete", col, "--recursive"])
