"""Issue #410: a discovery graph that can't be read used to be replaced by an
empty graph on the next save, losing the seeds and every triage decision."""

import json

import pytest

from zotero_cli.core.exceptions import DataFileError
from zotero_cli.core.services.snowball_graph import GRAPH_FORMAT_VERSION, SnowballGraphService


def _links_format_graph() -> dict:
    """What networkx < 3.6 wrote: edges under "links"."""
    return {
        "directed": True,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "10.1/a", "title": "Seed", "status": "ACCEPTED"},
            {"id": "10.1/b", "title": "Cited", "status": "PENDING"},
        ],
        "links": [{"source": "10.1/a", "target": "10.1/b"}],
    }


def test_links_format_files_still_load(tmp_path):
    path = tmp_path / "discovery_graph_1.json"
    path.write_text(json.dumps(_links_format_graph()))

    service = SnowballGraphService(path)

    assert service.graph.number_of_nodes() == 2
    assert service.graph.has_edge("10.1/a", "10.1/b")


def test_saved_files_carry_an_explicit_edge_key_and_format_version(tmp_path):
    path = tmp_path / "discovery_graph_1.json"
    path.write_text(json.dumps(_links_format_graph()))
    service = SnowballGraphService(path)

    service.save_graph()

    data = json.loads(path.read_text())
    assert data["graph"]["format_version"] == GRAPH_FORMAT_VERSION
    assert data["edges"] == [{"source": "10.1/a", "target": "10.1/b"}]
    assert SnowballGraphService(path).graph.number_of_nodes() == 2


@pytest.mark.parametrize("content", ['{"nodes": [', "not json at all", '{"nodes": 5}'])
def test_unreadable_graph_is_set_aside_and_the_command_stops(tmp_path, content):
    path = tmp_path / "discovery_graph_1.json"
    path.write_text(content)

    with pytest.raises(DataFileError, match="was moved to"):
        SnowballGraphService(path)

    assert not path.exists()  # nothing will overwrite it with an empty graph
    aside = list(tmp_path.glob("discovery_graph_1.json.corrupt-*"))
    assert len(aside) == 1
    assert aside[0].read_text() == content


def test_a_newer_format_is_refused_and_left_untouched(tmp_path):
    data = _links_format_graph()
    data["graph"] = {"format_version": GRAPH_FORMAT_VERSION + 1}
    path = tmp_path / "discovery_graph_1.json"
    path.write_text(json.dumps(data))

    with pytest.raises(DataFileError, match="newer zotero-cli"):
        SnowballGraphService(path)

    assert json.loads(path.read_text()) == data


def test_an_empty_file_starts_a_new_graph(tmp_path):
    path = tmp_path / "discovery_graph_1.json"
    path.write_text("")

    assert SnowballGraphService(path).graph.number_of_nodes() == 0


def test_main_reports_a_data_file_error_without_a_traceback(capsys, monkeypatch):
    import sys
    from unittest.mock import patch

    from zotero_cli.cli.main import main

    def boom(_args):
        raise DataFileError("graph unreadable; moved aside")

    with (
        patch.object(sys, "argv", ["zotero-cli", "system", "info"]),
        patch("zotero_cli.cli.commands.system_cmd.InfoCommand.execute", side_effect=boom),
        pytest.raises(SystemExit) as exc,
    ):
        main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Error: graph unreadable" in err
    assert "Traceback" not in err
