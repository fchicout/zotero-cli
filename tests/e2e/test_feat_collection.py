import time

import pytest


@pytest.mark.e2e
def test_collection_lifecycle(run_cli, timestamp):
    """
    Verifies the full lifecycle of a collection:
    Create -> List -> Rename -> Delete.
    """
    col_name = f"E2E_Coll_{timestamp}"
    new_name = f"E2E_Renamed_{timestamp}"

    try:
        # 1. Create
        res = run_cli(["collection", "create", col_name])
        assert res.returncode == 0
        # CLI Output: Created collection 'Name' (Key: XXXXX)
        assert f"Created collection '{col_name}'" in res.stdout

        # 2. List & Verify existence
        # Wait a moment for Zotero API to propagate
        time.sleep(2)
        list_res = run_cli(["collection", "list"])
        assert col_name in list_res.stdout

        # 3. Rename
        rename_res = run_cli(["collection", "rename", col_name, new_name])
        assert rename_res.returncode == 0

        time.sleep(2)
        list_after = run_cli(["collection", "list"])
        assert new_name in list_after.stdout
        assert col_name not in list_after.stdout

    finally:
        # 4. Cleanup (Delete)
        run_cli(["collection", "delete", col_name, "--recursive"])
        run_cli(["collection", "delete", new_name, "--recursive"])


@pytest.mark.e2e
def test_collection_clean(run_cli, temp_collection):
    """
    Verifies that 'collection clean' removes items but keeps the folder.
    """
    # 1. Import one item (Fixture already created collection)
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

    time.sleep(3)
    before_clean = run_cli(["item", "list", "--collection", temp_collection])
    assert "Attention" in before_clean.stdout

    # Action: Clean
    clean_res = run_cli(["collection", "clean", "--collection", temp_collection])
    assert clean_res.returncode == 0

    time.sleep(3)
    after_clean = run_cli(["item", "list", "--collection", temp_collection])
    assert "Showing 0 items" in after_clean.stdout

    # Folder should still exist
    list_res = run_cli(["collection", "list"])
    assert temp_collection in list_res.stdout
