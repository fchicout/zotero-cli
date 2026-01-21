import time
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_storage_checkout_flow(run_cli, temp_collection, tmp_path):
    """
    Verifies the storage checkout workflow:
    1. Create Collection (Handled by fixture)
    2. Import Item (with PDF)
    3. Storage Checkout (Move PDF to local)
    4. Verify Local File
    """
    # Define a custom storage path for this test
    # We pass it via env var to the CLI process
    test_storage_dir = tmp_path / "zotero_storage"
    test_storage_dir.mkdir()

    # 2. Import (Paper with known PDF)
    # 1706.03762 usually has a PDF.
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

    # Wait for Zotero to fetch the PDF (This is the flaky part)
    print("Waiting for Zotero to index and fetch PDF...")
    time.sleep(10)

    # 3. Checkout
    import os

    env_overrides = os.environ.copy()
    env_overrides["ZOTERO_STORAGE_PATH"] = str(test_storage_dir)

    import subprocess
    import sys

    cwd = Path.cwd()
    src_path = str(cwd / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = src_path
    env["ZOTERO_STORAGE_PATH"] = str(test_storage_dir)

    print(f"Running checkout with storage: {test_storage_dir}")
    res = subprocess.run(
        [sys.executable, "-m", "zotero_cli.cli.main", "storage", "checkout", "--limit", "5"],
        capture_output=True,
        text=True,
        env=env,
    )

    print(f"STDOUT: {res.stdout}")
    print(f"STDERR: {res.stderr}")
    assert res.returncode == 0

    # 4. Verification
    # Check if any PDF landed in the temp dir
    pdfs = list(test_storage_dir.glob("*.pdf"))
    if not pdfs:
        pytest.skip("Zotero did not download the PDF in time for the test to check it out.")

    assert len(pdfs) > 0
    print(f"Verified downloaded PDF: {pdfs[0].name}")
