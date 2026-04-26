import argparse
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.slr.snowball_cmd import SnowballCommand


@pytest.fixture
def mock_deps():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mw, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_snowball_ingestion_service") as ms, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_snowball_graph_service") as mg, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as mj:
        yield mw.return_value, ms.return_value, mg.return_value, mj.return_value

def test_snowball_command_seed(mock_deps, capsys):
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps
    from zotero_cli.core.zotero_item import ZoteroItem

    mock_item = ZoteroItem(key="K1", version=1, item_type="journalArticle", doi="10.1/1")
    mock_gw.get_item.return_value = mock_item

    args = argparse.Namespace(verb="snowball", snow_verb="seed", keys="K1", collection=None, backward=True, forward=False, generation=1, user=False)
    SnowballCommand.execute(mock_gw, args)

    out = capsys.readouterr().out
    assert "Enqueued 1 discovery jobs" in out

def test_snowball_command_graph(mock_deps, capsys):
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps
    mock_graph.to_mermaid.return_value = "graph TD; A-->B"

    args = argparse.Namespace(verb="snowball", snow_verb="export", format="mermaid", collection="Col1", output=None, user=False)
    SnowballCommand.execute(mock_gw, args)

    out = capsys.readouterr().out
    assert "graph TD; A-->B" in out

def test_snowball_command_status(mock_deps, capsys):
    mock_gw, mock_ingest, mock_graph, mock_jq = mock_deps
    mock_graph.get_stats.return_value = {"total_nodes": 10, "total_edges": 5}

    args = argparse.Namespace(verb="snowball", snow_verb="status", collection="Col1", user=False)
    SnowballCommand.execute(mock_gw, args)

    out = capsys.readouterr().out
    assert "Snowballing Discovery Graph Status" in out
    assert "10" in out # Nodes
