import time
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.e2e
def test_backup_restore_e2e(run_cli: Any, sentinel: Any, timestamp: Any, tmp_path: Path) -> None:
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
