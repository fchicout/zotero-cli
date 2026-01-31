import os
import tempfile
from pathlib import Path

import pytest

from zotero_cli.core.services.snowball_graph import SnowballGraphService


@pytest.fixture
def temp_storage():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield Path(path)
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def graph_service(temp_storage):
    return SnowballGraphService(temp_storage)


def test_get_stats(graph_service):
    # Setup graph
    seed = {"doi": "10.1001/seed", "title": "Seed"}
    cand1 = {"doi": "10.1002/cand1", "title": "Cand 1"}
    cand2 = {"doi": "10.1002/cand2", "title": "Cand 2"}

    graph_service.add_candidate(seed, generation=0)
    graph_service.update_status(seed["doi"], SnowballGraphService.STATUS_ACCEPTED)

    graph_service.add_candidate(cand1, parent_doi=seed["doi"], direction="forward", generation=1)
    graph_service.add_candidate(cand2, parent_doi=seed["doi"], direction="forward", generation=1)
    graph_service.update_status(cand2["doi"], "IMPORTED")

    stats = graph_service.get_stats()

    assert stats["total_nodes"] == 3
    assert stats["total_edges"] == 2
    assert stats["by_status"][SnowballGraphService.STATUS_ACCEPTED] == 1
    assert stats["by_status"][SnowballGraphService.STATUS_PENDING] == 1
    assert stats["by_status"]["IMPORTED"] == 1
    assert stats["by_generation"][0] == 1
    assert stats["by_generation"][1] == 2


def test_to_mermaid(graph_service):
    seed = {"doi": "10.1001/seed", "title": "Seed Paper"}
    cand = {"doi": "10.1002/cand", "title": "Candidate Paper"}

    graph_service.add_candidate(seed, generation=0)
    graph_service.add_candidate(cand, parent_doi=seed["doi"], direction="forward", generation=1)

    mermaid = graph_service.to_mermaid()

    assert mermaid.startswith("graph TD")
    assert "10.1001/seed" in mermaid
    assert "10.1002/cand" in mermaid
    assert "10.1001/seed --> 10.1002/cand" in mermaid
