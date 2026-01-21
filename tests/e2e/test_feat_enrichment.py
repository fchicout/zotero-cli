import re
import time

import pytest


@pytest.mark.e2e
def test_item_hydrate_dry_run(run_cli, temp_collection):
    """
    Verifies the 'item hydrate' command integration and reporting.
    """
    # 1. Import a known ArXiv paper (SimSiam)
    # Even if it already has a DOI, we want to verify the command logic executes.
    arxiv_id = "2103.10433"

    run_cli(
        [
            "import",
            "arxiv",
            "--query",
            f"id:{arxiv_id}",
            "--limit",
            "1",
            "--collection",
            temp_collection,
        ]
    )

    # 2. Get the key
    time.sleep(3)
    list_res = run_cli(["item", "list", "--collection", temp_collection])
    keys = re.findall(r"\b([A-Z0-9]{8})\b", list_res.stdout)
    assert keys, "Item key not found after import"
    item_key = keys[0]

    # 3. Action: Hydrate (Dry Run)
    # Note: If it already has DOI/Journal, it might say "No items needed hydration"
    res = run_cli(["item", "hydrate", item_key, "--dry-run"])

    assert res.returncode == 0
    # Either it shows the report table or the "No items needed" message.
    # Both prove the CLI -> Service integration is working.
    assert "Hydration Report" in res.stdout or "No items needed hydration" in res.stdout


@pytest.mark.e2e
def test_item_hydrate_help(run_cli):
    """Verifies help output."""
    res = run_cli(["item", "hydrate", "--help"])
    assert res.returncode == 0
    # Just check for core flags to avoid specific phrasing issues
    assert "--dry-run" in res.stdout
    assert "--collection" in res.stdout
    assert "--all" in res.stdout
