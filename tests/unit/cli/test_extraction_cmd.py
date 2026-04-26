import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.slr.extraction_cmd import ExtractionCommand


@pytest.fixture
def mock_deps():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mg, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_extraction_service") as me:
        yield mg.return_value, me.return_value

def test_extraction_command_key(mock_deps, capsys):
    mock_gateway, mock_service = mock_deps
    from zotero_cli.core.zotero_item import ZoteroItem

    mock_item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="Paper 1")
    mock_gateway.get_item.return_value = mock_item

    with patch("zotero_cli.cli.tui.factory.TUIFactory.get_extraction_tui") as mock_tui_factory:
        mock_tui = mock_tui_factory.return_value
        args = argparse.Namespace(verb="extraction", key="K1", collection=None, agent=False, persona=None, export=None, user=False)
        ExtractionCommand.execute(args)

        mock_tui.run_extraction.assert_called_once_with([mock_item], agent=False, persona=None)

def test_extraction_command_collection(mock_deps, capsys):
    mock_gateway, mock_service = mock_deps
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_item = MagicMock()
    mock_gateway.get_items_in_collection.return_value = [mock_item]

    with patch("zotero_cli.cli.tui.factory.TUIFactory.get_extraction_tui") as mock_tui_factory:
        mock_tui = mock_tui_factory.return_value
        args = argparse.Namespace(verb="extraction", key=None, collection="MyCol", agent=True, persona="Paula", export=None, user=False)
        ExtractionCommand.execute(args)

        mock_tui.run_extraction.assert_called_once_with([mock_item], agent=True, persona="Paula")

def test_extraction_command_no_items(mock_deps, capsys):
    mock_gateway, mock_service = mock_deps
    mock_gateway.get_item.return_value = None

    args = argparse.Namespace(verb="extraction", key="MISSING", collection=None, agent=False, persona=None, export=None, user=False)
    ExtractionCommand.execute(args)

    out = capsys.readouterr().out
    assert "No items found for extraction" in out
