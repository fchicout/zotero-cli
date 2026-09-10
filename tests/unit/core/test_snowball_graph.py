import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

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


def test_update_status_records_reason_and_depth(graph_service):
    """Issue #211: accept/reject decisions can optionally record why and
    how thoroughly the paper was evaluated, mirroring SDB screening's
    reason/evidence audit trail."""
    doi = "10.1001/test"
    graph_service.add_candidate({"doi": doi, "title": "Test Paper"})

    graph_service.update_status(
        doi, SnowballGraphService.STATUS_ACCEPTED, reason="Directly relevant", depth="full_text"
    )

    node = graph_service.graph.nodes[doi]
    assert node["status"] == SnowballGraphService.STATUS_ACCEPTED
    assert node["decision_reason"] == "Directly relevant"
    assert node["decision_depth"] == "full_text"


def test_update_status_without_reason_or_depth_omits_them(graph_service):
    doi = "10.1001/test"
    graph_service.add_candidate({"doi": doi, "title": "Test Paper"})

    graph_service.update_status(doi, SnowballGraphService.STATUS_REJECTED)

    node = graph_service.graph.nodes[doi]
    assert "decision_reason" not in node
    assert "decision_depth" not in node


def test_get_accepted_dois(graph_service):
    """Issue #206: re-seeding the next generation reads ACCEPTED DOIs
    directly off the graph, optionally scoped to one generation."""
    gen1_doi = "10.1001/gen1"
    gen2_doi = "10.1001/gen2"
    pending_doi = "10.1001/pending"

    graph_service.add_candidate({"doi": gen1_doi, "title": "Gen 1"}, generation=1)
    graph_service.update_status(gen1_doi, SnowballGraphService.STATUS_ACCEPTED)

    graph_service.add_candidate({"doi": gen2_doi, "title": "Gen 2"}, generation=2)
    graph_service.update_status(gen2_doi, SnowballGraphService.STATUS_ACCEPTED)

    graph_service.add_candidate({"doi": pending_doi, "title": "Pending"}, generation=1)

    assert set(graph_service.get_accepted_dois()) == {gen1_doi, gen2_doi}
    assert graph_service.get_accepted_dois(generation=1) == [gen1_doi]
    assert graph_service.get_accepted_dois(generation=2) == [gen2_doi]
    assert graph_service.get_accepted_dois(generation=99) == []


def test_to_json(graph_service):
    """Issue #208: `slr snowball export --format json` had no
    implementation at all - to_json() gives it something real to export,
    the same node-link shape save_graph() already persists to disk."""
    graph_service.add_candidate({"doi": "10.1001/a", "title": "Paper A"}, generation=0)
    graph_service.add_candidate(
        {"doi": "10.1001/b", "title": "Paper B"},
        parent_doi="10.1001/a",
        direction="forward",
        generation=1,
    )

    output = graph_service.to_json()
    data = json.loads(output)

    node_ids = {node["id"] for node in data["nodes"]}
    assert node_ids == {"10.1001/a", "10.1001/b"}
    assert len(data["edges"]) == 1


def test_to_json_empty_graph(graph_service):
    data = json.loads(graph_service.to_json())
    assert data["nodes"] == []
    assert data["edges"] == []


def test_save_graph_leaves_no_tmp_file_and_writes_valid_json(graph_service, temp_storage):
    """Regression test for Issue #299: save_graph must write via a temp
    file + atomic rename, not a plain truncating write - a crash mid-write
    of the latter could leave a corrupt/partial JSON file behind."""
    graph_service.add_candidate({"doi": "10.1001/a", "title": "Paper A"}, generation=0)
    graph_service.save_graph()

    tmp_path = temp_storage.with_suffix(temp_storage.suffix + ".tmp")
    assert not tmp_path.exists()

    with open(temp_storage, encoding="utf-8") as f:
        data = json.load(f)
    assert {node["id"] for node in data["nodes"]} == {"10.1001/a"}


def test_save_graph_holds_file_lock_for_mutual_exclusion(graph_service, temp_storage):
    """Regression test for Issue #299: save_graph must actually hold
    self._lock across the write, not just import filelock - verified by
    forcing overlap: a slow writer must block a second writer's lock
    acquisition until the first releases it."""
    import threading

    graph_service.add_candidate({"doi": "10.1001/a", "title": "A"}, generation=0)

    original_dump = json.dump
    entered_write = threading.Event()
    release_writer = threading.Event()

    def slow_dump(*args, **kwargs):
        entered_write.set()
        release_writer.wait(timeout=5)
        return original_dump(*args, **kwargs)

    second_writer_locked_out = []

    def second_save():
        from filelock import Timeout

        entered_write.wait(timeout=5)
        # If the lock is genuinely held by the first writer, this
        # acquisition attempt must time out rather than succeed.
        try:
            graph_service._lock.acquire(timeout=0.2)
        except Timeout:
            second_writer_locked_out.append(True)
        else:
            second_writer_locked_out.append(False)
            graph_service._lock.release()

    with patch("zotero_cli.core.services.snowball_graph.json.dump", side_effect=slow_dump):
        t1 = threading.Thread(target=graph_service.save_graph)
        t2 = threading.Thread(target=second_save)
        t1.start()
        t2.start()
        t2.join(timeout=6)
        release_writer.set()
        t1.join(timeout=6)

    assert second_writer_locked_out == [True]


def test_save_graph_survives_concurrent_writes_without_corruption(temp_storage):
    """Concurrent save_graph() calls (e.g. two discovery/review sessions
    on the same graph) must never produce a torn/unparseable JSON file."""
    import threading

    services = [SnowballGraphService(temp_storage) for _ in range(5)]
    for i, service in enumerate(services):
        service.add_candidate({"doi": f"10.1001/{i}", "title": f"Paper {i}"}, generation=0)

    barrier = threading.Barrier(len(services))

    def save(service):
        barrier.wait()
        service.save_graph()

    threads = [threading.Thread(target=save, args=(s,)) for s in services]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with open(temp_storage, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["nodes"]) == 1
