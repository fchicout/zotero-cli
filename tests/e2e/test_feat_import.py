import time

import pytest


@pytest.mark.e2e
def test_import_arxiv_basic(run_cli, timestamp):
    """
    Verifies that importing from arXiv correctly populates a collection.
    """
    col_name = f"E2E_Import_Arxiv_{timestamp}"

    try:
        run_cli(["collection", "create", col_name])

        # Action: Import (Deterministic via ID)
        res = run_cli(
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
        assert res.returncode == 0
        assert "Imported 1 items" in res.stdout

        # Verify content
        time.sleep(3)
        list_res = run_cli(["item", "list", "--collection", col_name])

        # Robustness: Extract key and inspect detail to avoid Table Truncation issues
        import re

        keys = re.findall(r"\b([A-Z0-9]{8})\b", list_res.stdout)
        assert keys, "No items found in list output"
        item_key = keys[0]

        show_res = run_cli(["item", "inspect", item_key])
        assert "Attention Is All You Need" in show_res.stdout
        assert "Vaswani" in show_res.stdout
    finally:
        run_cli(["collection", "delete", col_name, "--recursive"])


@pytest.mark.e2e
def test_import_arxiv_invalid_query(run_cli, timestamp):
    """
    Verifies that invalid queries are handled gracefully.
    """
    col_name = f"E2E_Import_Fail_{timestamp}"
    try:
        run_cli(["collection", "create", col_name])

        # Action: Import with nonsensical query
        res = run_cli(
            ["import", "arxiv", "--query", "aksdjhfaskjdhfaksjdhf", "--collection", col_name]
        )
        # It shouldn't crash, but it should report 0 items
        assert res.returncode == 0
        assert "Imported 0 items" in res.stdout
    finally:
        run_cli(["collection", "delete", col_name, "--recursive"])
