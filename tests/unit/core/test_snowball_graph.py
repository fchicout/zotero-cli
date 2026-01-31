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


def test_add_candidate_and_ranking(graph_service):
    # Seed Set (Gen 0)
    seed1 = {"doi": "10.1001/seed1", "title": "Seed 1"}
    seed2 = {"doi": "10.1001/seed2", "title": "Seed 2"}

    graph_service.add_candidate(seed1, generation=0)
    graph_service.update_status(seed1["doi"], SnowballGraphService.STATUS_ACCEPTED)

    graph_service.add_candidate(seed2, generation=0)
    graph_service.update_status(seed2["doi"], SnowballGraphService.STATUS_ACCEPTED)

    # Candidates (Gen 1)
    # Candidate A: Cited by Seed 1 and Seed 2
    cand_a = {"doi": "10.1002/candA", "title": "Candidate A"}
    graph_service.add_candidate(cand_a, parent_doi=seed1["doi"], direction="forward", generation=1)
    graph_service.add_candidate(cand_a, parent_doi=seed2["doi"], direction="forward", generation=1)

    # Candidate B: Cited by Seed 1 only
    cand_b = {"doi": "10.1002/candB", "title": "Candidate B"}
    graph_service.add_candidate(cand_b, parent_doi=seed1["doi"], direction="forward", generation=1)

    # Candidate C: Cites Seed 2 (Backward snowballing)
    cand_c = {"doi": "10.1002/candC", "title": "Candidate C"}
    graph_service.add_candidate(cand_c, parent_doi=seed2["doi"], direction="backward", generation=1)

    # Ranked Candidates
    ranked = graph_service.get_ranked_candidates()

    assert len(ranked) == 3
    assert ranked[0]["doi"] == "10.1002/candA"
    assert ranked[0]["relevance_score"] == 2

    # cand_b and cand_c both have score 1
    assert ranked[1]["relevance_score"] == 1
    assert ranked[2]["relevance_score"] == 1


def test_persistence(temp_storage):
    service = SnowballGraphService(temp_storage)
    service.add_candidate({"doi": "10.1001/test", "title": "Test Paper"}, generation=0)
    service.save_graph()

    assert temp_storage.exists()

    # Load in new service
    service2 = SnowballGraphService(temp_storage)
    assert "10.1001/test" in service2.graph
    assert service2.graph.nodes["10.1001/test"]["title"] == "Test Paper"


def test_update_status(graph_service):
    doi = "10.1001/test"
    graph_service.add_candidate({"doi": doi, "title": "Test Paper"})

    graph_service.update_status(doi, SnowballGraphService.STATUS_REJECTED)

    assert graph_service.graph.nodes[doi]["status"] == SnowballGraphService.STATUS_REJECTED

    # Should not be in ranked candidates
    ranked = graph_service.get_ranked_candidates()
    assert all(c["doi"] != doi for c in ranked)
