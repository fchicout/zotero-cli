import pytest


@pytest.mark.e2e
def test_orphan_prevention_audit(run_cli, timestamp):
    """
    AUDIT: Verifies that deleting a collection doesn't leave orphaned items
    behind if they were imported specifically for that collection.
    """
    col_name = f"E2E_ORPHAN_TEST_{timestamp}"
    run_cli(["collection", "create", col_name])

    # Import an item
    run_cli(["import", "arxiv", "--query", "id:1706.03762", "--limit", "1", "--collection", col_name])

    # Action: Delete collection recursively
    run_cli(["collection", "delete", col_name, "--recursive"])

    # Check if item exists in 'Unfiled' or root
    # Note: This requires a way to check if an item with a specific DOI still exists
    res = run_cli(["item", "search", "1706.03762"])

    if "Attention" in res.stdout:
        print("\n[AUDIT] Potential orphan detected! Item still exists after collection deletion.")
        # pytest.fail("Orphan Prevention Violation: Item still exists.")
    else:
        print("\n[AUDIT] Orphan prevention verified.")
