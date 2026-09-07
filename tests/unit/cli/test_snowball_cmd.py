import argparse
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.slr.snowball_cmd import SnowballCommand


@pytest.fixture
def mock_deps():
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mw,
        patch("zotero_cli.infra.factory.GatewayFactory.get_snowball_ingestion_service") as ms,
        patch("zotero_cli.infra.factory.GatewayFactory.get_snowball_graph_service") as mg,
        patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as mj,
    ):
        yield mw.return_value, ms.return_value, mg.return_value, mj.return_value


def test_snowball_command_seed(mock_deps, capsys):
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps
    from zotero_cli.core.zotero_item import ZoteroItem

    mock_item = ZoteroItem(key="K1", version=1, item_type="journalArticle", doi="10.1/1")
    mock_gw.get_item.return_value = mock_item

    args = argparse.Namespace(
        verb="snowball",
        snow_verb="seed",
        keys="K1",
        collection=None,
        backward=True,
        forward=False,
        generation=1,
        user=False,
    )
    SnowballCommand.execute(mock_gw, args)

    out = capsys.readouterr().out
    assert "Enqueued 1 discovery jobs" in out


def test_snowball_command_seed_from_dois(mock_deps, capsys):
    """Issue #206: --dois seeds directly from bare DOIs, no Zotero lookup."""
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps

    args = argparse.Namespace(
        verb="snowball",
        snow_verb="seed",
        keys=None,
        collection=None,
        dois="10.1/a, 10.1/b",
        from_accepted=False,
        from_generation=None,
        backward=True,
        forward=False,
        generation=2,
        user=False,
    )
    SnowballCommand.execute(mock_gw, args)

    mock_gw.get_item.assert_not_called()
    out = capsys.readouterr().out
    assert "Enqueued 2 discovery jobs" in out


def test_snowball_command_seed_from_accepted(mock_deps, capsys):
    """Issue #206: --from-accepted re-seeds from this graph's own ACCEPTED
    DOIs, optionally scoped to --from-generation."""
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps
    mock_graph.get_accepted_dois.return_value = ["10.1/accepted1", "10.1/accepted2"]

    args = argparse.Namespace(
        verb="snowball",
        snow_verb="seed",
        keys=None,
        collection=None,
        dois=None,
        from_accepted=True,
        from_generation=1,
        backward=False,
        forward=True,
        generation=2,
        user=False,
    )
    SnowballCommand.execute(mock_gw, args)

    mock_graph.get_accepted_dois.assert_called_once_with(generation=1)
    out = capsys.readouterr().out
    assert "Enqueued 2 discovery jobs" in out


def test_snowball_command_graph(mock_deps, capsys):
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps
    mock_graph.to_mermaid.return_value = "graph TD; A-->B"

    args = argparse.Namespace(
        verb="snowball",
        snow_verb="export",
        format="mermaid",
        collection="Col1",
        output=None,
        user=False,
    )
    SnowballCommand.execute(mock_gw, args)

    out = capsys.readouterr().out
    assert "graph TD; A-->B" in out


def test_snowball_command_export_json(mock_deps, capsys):
    """Issue #208: `export --format json` must produce real output, not
    the previous no-op `pass`."""
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps
    mock_graph.to_json.return_value = '{"nodes": [], "links": []}'

    args = argparse.Namespace(
        verb="snowball",
        snow_verb="export",
        format="json",
        collection="Col1",
        output=None,
        user=False,
    )
    SnowballCommand.execute(mock_gw, args)

    mock_graph.to_json.assert_called_once()
    out = capsys.readouterr().out
    assert '{"nodes": [], "links": []}' in out


def test_snowball_command_status(mock_deps, capsys):
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps
    mock_graph.get_stats.return_value = {"total_nodes": 10, "total_edges": 5}

    args = argparse.Namespace(verb="snowball", snow_verb="status", collection="Col1", user=False)
    SnowballCommand.execute(mock_gw, args)

    out = capsys.readouterr().out
    assert "Snowballing Discovery Graph Status" in out
    assert "10" in out  # Nodes
