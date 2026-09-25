import json
import time

import pytest


@pytest.mark.e2e
def test_collection_lifecycle(run_cli, sentinel, timestamp):
    """
    Verifies the full lifecycle of a collection:
    Create -> List -> Rename -> Delete.
    Uses 'sentinel' for robust cleanup.
    """
    col_name = f"E2E_Coll_{timestamp}"
    new_name = f"E2E_Renamed_{timestamp}"

    # 1. Create
    res = sentinel.create_collection(col_name)
    assert res.returncode == 0
    assert f"Created collection '{col_name}'" in res.stdout

    # 2. List & Verify existence
    time.sleep(5)
    list_res = run_cli(["collection", "list"])
    assert col_name in list_res.stdout

    # 3. Rename
    rename_res = run_cli(["collection", "rename", "--key", col_name, "--name", new_name])
    assert rename_res.returncode == 0

    # Track the new name for cleanup as well
    sentinel.track(new_name)

    time.sleep(5)
    list_after = run_cli(["collection", "list"])
    assert new_name in list_after.stdout
    assert col_name not in list_after.stdout

    # 4. Cleanup is handled by sentinel fixture automatically


@pytest.mark.e2e
def test_collection_clean(run_cli, temp_collection):
    """
    Verifies that 'collection clean' previews by default, then takes the
    items out of the collection without deleting them (Issue #364), and
    keeps the folder. 'temp_collection' fixture now uses 'sentinel' internally.
    """
    # 1. Import one item
    run_cli(
        [
            "import",
            "arxiv",
            "--query",
            "id:1706.03762",
            "--limit",
            "1",
            "--collection",
            temp_collection,
        ]
    )

    time.sleep(10)
    before_clean = run_cli(
        ["item", "list", "--collection", temp_collection, "--fields", "key,title", "--format", "json"]
    )
    rows = json.loads(before_clean.stdout)
    assert any("Attention" in r["title"] for r in rows)
    keys = [r["key"] for r in rows]

    try:
        # Preview: nothing changes
        preview = run_cli(["collection", "clean", "--collection", temp_collection])
        assert preview.returncode == 0 and "Preview only" in preview.stdout
        still = run_cli(["item", "list", "--collection", temp_collection])
        assert "Attention" in still.stdout

        # Action: Clean
        clean_res = run_cli(["collection", "clean", "--collection", temp_collection, "--execute"])
        assert clean_res.returncode == 0

        time.sleep(3)
        after_clean = run_cli(["item", "list", "--collection", temp_collection])
        assert "Showing 0 items" in after_clean.stdout

        # The items still exist in the library
        for key in keys:
            assert "Attention" in run_cli(["item", "inspect", "--key", key]).stdout

        # Folder should still exist
        list_res = run_cli(["collection", "list"])
        assert temp_collection in list_res.stdout
    finally:
        # The cleaned items are now unfiled; delete them so the test leaves
        # nothing behind in the library.
        for key in keys:
            run_cli(["item", "delete", "--key", key])
