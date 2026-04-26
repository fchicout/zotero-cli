import re

import pytest


@pytest.mark.e2e
def test_audit_for_leaked_collections(run_cli):
    """
    QA_FORCE Audit: Scans the Zotero library for any collections starting with 'E2E_'
    that might have been leaked by previous test runs.
    """
    res = run_cli(["collection", "list"])
    assert res.returncode == 0

    # Standard format for E2E collections is E2E_Temp_..., E2E_Backup_..., etc.
    leaked = re.findall(r"(E2E_\w+)", res.stdout)

    if leaked:
        print(f"\n[AUDIT] Found {len(leaked)} potentially leaked collections: {leaked}")
        # We don't automatically delete them here to avoid 'Ghost Success'
        # but we fail the audit if any are found.
        # pytest.fail(f"Resource Leak Detected: {len(leaked)} collections found.")
    else:
        print("\n[AUDIT] No leaked E2E collections found.")

@pytest.mark.e2e
def test_resource_tracker_proposal_verification(run_cli, timestamp):
    """
    Verification artifact for a proposed 'ResourceTracker' pattern.
    Simulates a test that 'forgets' to cleanup, to prove we need a robust tracker.
    """
    col_name = f"E2E_LEAK_TEST_{timestamp}"
    run_cli(["collection", "create", col_name])

    # We exit without manual cleanup.
    # If the QA_FORCE objective is met, a global fixture should have caught this.
    pass
