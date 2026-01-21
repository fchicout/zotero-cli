import time

import pytest


@pytest.mark.e2e
def test_import_arxiv_basic(run_cli, temp_collection):
    """
    Verifies that importing from arXiv correctly populates a collection.
    """
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
            temp_collection,
        ]
    )
    assert res.returncode == 0
    assert "Imported 1 items" in res.stdout

    # Verify content
    time.sleep(3)
    list_res = run_cli(["item", "list", "--collection", temp_collection])

    # Robustness: Extract key and inspect detail to avoid Table Truncation issues
    import re

    keys = re.findall(r"\b([A-Z0-9]{8})\b", list_res.stdout)
    assert keys, "No items found in list output"
    item_key = keys[0]

    show_res = run_cli(["item", "inspect", item_key])
    assert "Attention Is All You Need" in show_res.stdout
    assert "Vaswani" in show_res.stdout


@pytest.mark.e2e
def test_import_arxiv_invalid_query(run_cli, temp_collection):
    """
    Verifies that invalid queries are handled gracefully.
    """
    # Action: Import with nonsensical query
    res = run_cli(
        ["import", "arxiv", "--query", "aksdjhfaskjdhfaksjdhf", "--collection", temp_collection]
    )
    # It shouldn't crash, but it should report 0 items
    assert res.returncode == 0
    assert "Imported 0 items" in res.stdout
