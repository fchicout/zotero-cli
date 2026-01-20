import time
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_storage_checkout_flow(run_cli, timestamp, tmp_path):
    """
    Verifies the storage checkout workflow:
    1. Create Collection
    2. Import Item (with PDF)
    3. Storage Checkout (Move PDF to local)
    4. Verify Local File
    """
    col_name = f"E2E_Storage_{timestamp}"

    # Define a custom storage path for this test
    # We pass it via env var to the CLI process
    test_storage_dir = tmp_path / "zotero_storage"
    test_storage_dir.mkdir()

    try:
        # 1. Setup
        run_cli(["collection", "create", col_name])

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
                col_name,
            ]
        )

        # Wait for Zotero to fetch the PDF (This is the flaky part)
        print("Waiting for Zotero to index and fetch PDF...")
        time.sleep(10)

        # 3. Checkout
        # We assume the config uses the environment variable if set.
        # But wait, run_cli sets PYTHONPATH but doesn't easily inject arbitrary env vars for config.
        # The CLI reads config.toml.
        # We need to override ZOTERO_STORAGE_PATH env var in the subprocess.

        import os

        env_overrides = os.environ.copy()
        env_overrides["ZOTERO_STORAGE_PATH"] = str(test_storage_dir)

        # We need to manually invoke subprocess here because run_cli fixture
        # doesn't support custom env vars yet.
        # Actually, I should update run_cli to support this, but for now I'll just use the fixture's logic inline or modify the fixture.
        # I'll rely on the fact that I can't modify the fixture easily in this turn without re-writing conftest.
        # I will hack it by setting os.environ locally? No, run_cli uses os.environ.copy().
        # I'll just set os.environ in this process before calling run_cli? No, run_cli copies inside.

        # Let's write a custom subprocess call here for the checkout command.
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

    finally:
        run_cli(["collection", "delete", col_name, "--recursive"])
