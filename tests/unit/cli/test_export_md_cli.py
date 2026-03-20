import sys
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from zotero_cli.cli.main import main


@pytest.fixture
def mock_factory():
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_attachment_service") as mock_att_get,
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_zot_get,
        patch("zotero_cli.core.config.get_config") as mock_config,
    ):
        mock_att = mock_att_get.return_value
        mock_gateway = mock_zot_get.return_value
        yield {
            "attachment": mock_att,
            "gateway": mock_gateway,
            "config": mock_config.return_value,
        }


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")


def test_item_export_md_success(mock_factory, env_vars, capsys, tmp_path):
    mock_att = mock_factory["attachment"]
    # ItemCommand calls bulk_export_markdown([item], ...)
    mock_att.bulk_export_markdown.return_value = {
        "total": 1, "success": 1, "failed": 0, "skipped": 0
    }
    
    # Mock ZoteroItem
    mock_item = MagicMock()
    mock_item.key = "KEY1"
    mock_item.title = "Test Paper"
    mock_factory["gateway"].get_item.return_value = mock_item

    test_args = ["zotero-cli", "item", "export", "--key", "KEY1", "--format", "md", "--output", str(tmp_path)]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "Success!" in out
    assert str(tmp_path) in out
    mock_att.bulk_export_markdown.assert_called_once()


def test_collection_export_md_success(mock_factory, env_vars, capsys, tmp_path):
    mock_att = mock_factory["attachment"]
    # The collection command calls _export_item_markdown in a loop for progress
    mock_att._export_item_markdown.return_value = "success"
    
    mock_gateway = mock_factory["gateway"]
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_collection.return_value = {"key": "COL1", "data": {"name": "MyCol"}}
    
    mock_item = MagicMock()
    mock_item.key = "K1"
    mock_item.title = "Paper 1"
    mock_gateway.get_items_in_collection.return_value = [mock_item]

    test_args = ["zotero-cli", "collection", "export", "--name", "MyCol", "--format", "md", "--output", str(tmp_path)]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "Export Summary:" in out
    assert "Success: 1" in out
    mock_att._export_item_markdown.assert_called_once()
