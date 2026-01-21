import time

import pytest


@pytest.mark.e2e
def test_slr_graph_execution(run_cli, temp_collection):
    """
    Verifies that 'zotero-cli slr graph' generates a valid DOT file.
    """
    # 1. Import a paper to ensure there is something to graph
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

    # 2. Execute Graph command
    res = run_cli(["slr", "graph", "--collections", temp_collection])

    assert res.returncode == 0
    # Output should be a DOT format digraph
    assert "digraph" in res.stdout
    assert "CitationGraph" in res.stdout
    assert "rankdir" in res.stdout
    assert "}" in res.stdout
