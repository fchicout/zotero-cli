"""Snowball decisions are saved in batches, compactly (Issue #435)."""

import json
from unittest.mock import patch

import pytest

from zotero_cli.core.services.snowball_graph import SnowballGraphService


@pytest.fixture
def service(tmp_path):
    graph = SnowballGraphService(tmp_path / "graph.json")
    for n in range(60):
        graph.add_candidate({"doi": f"10.1/{n}", "title": f"Paper {n}"})
    graph.save_graph()
    return graph


def test_decisions_are_written_every_save_every(service):
    with patch.object(SnowballGraphService, "save_graph", autospec=True,
                      wraps=SnowballGraphService.save_graph) as save:
        for n in range(SnowballGraphService.SAVE_EVERY - 1):
            service.update_status(f"10.1/{n}", SnowballGraphService.STATUS_ACCEPTED)
        assert save.call_count == 0
        service.update_status("10.1/59", SnowballGraphService.STATUS_REJECTED)
        assert save.call_count == 1


def test_flush_writes_pending_decisions_only_when_there_are_some(service, tmp_path):
    service.update_status("10.1/1", SnowballGraphService.STATUS_ACCEPTED, reason="fits")
    with patch.object(SnowballGraphService, "save_graph", autospec=True,
                      wraps=SnowballGraphService.save_graph) as save:
        service.flush()
        service.flush()
    assert save.call_count == 1

    reloaded = SnowballGraphService(tmp_path / "graph.json")
    assert reloaded.graph.nodes["10.1/1"]["status"] == SnowballGraphService.STATUS_ACCEPTED
    assert reloaded.graph.nodes["10.1/1"]["decision_reason"] == "fits"


def test_a_slow_session_still_saves_every_interval(service):
    with (
        # Past the interval, not on it: (t + 30.0) - t can be 29.999... in
        # floating point, which made this test depend on the clock value.
        patch("zotero_cli.core.services.snowball_graph.time.monotonic",
              return_value=service._last_save + SnowballGraphService.SAVE_INTERVAL + 1),
        patch.object(SnowballGraphService, "save_graph", autospec=True) as save,
    ):
        service.update_status("10.1/2", SnowballGraphService.STATUS_ACCEPTED)
    assert save.call_count == 1


def test_the_stored_file_is_compact_and_loads(service, tmp_path):
    text = (tmp_path / "graph.json").read_text()
    assert "\n" not in text
    assert len(json.loads(text)["nodes"]) == 60
    assert "\n" in service.to_json()  # the export stays readable
