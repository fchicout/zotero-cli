import argparse
from unittest.mock import MagicMock, patch

import pytest
from zotero_cli.cli.commands.search_cmd import SearchCommand
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        yield mock_get.return_value


@pytest.fixture
def search_cmd():
    return SearchCommand()


def test_search_by_doi(search_cmd, mock_gateway):
    args = argparse.Namespace(query=None, doi="10.1234/5678", title=None, limit=50, user=False)
    
    item = ZoteroItem.from_raw_zotero_item({
        "key": "KEY1",
        "data": {"title": "Test Paper", "DOI": "10.1234/5678", "creators": [], "date": "2023"}
    })
    mock_gateway.get_items_by_doi.return_value = [item]

    search_cmd.execute(args)

    mock_gateway.get_items_by_doi.assert_called_once_with("10.1234/5678")


def test_search_by_title(search_cmd, mock_gateway):
    args = argparse.Namespace(query=None, doi=None, title="Transformer", limit=50, user=False)
    
    item = ZoteroItem.from_raw_zotero_item({
        "key": "KEY1",
        "data": {"title": "Attention is all you need", "creators": [], "date": "2017"}
    })
    mock_gateway.search_items.return_value = [item]

    search_cmd.execute(args)

    mock_gateway.search_items.assert_called_once()
    query = mock_gateway.search_items.call_args[0][0]
    assert query.q == "Transformer"
    assert query.qmode == "titleCreatorYear"


def test_search_by_query(search_cmd, mock_gateway):
    args = argparse.Namespace(query="Deep Learning", doi=None, title=None, limit=50, user=False)
    
    item = ZoteroItem.from_raw_zotero_item({
        "key": "KEY1",
        "data": {"title": "Deep Learning Book", "creators": [], "date": "2016"}
    })
    mock_gateway.search_items.return_value = [item]

    search_cmd.execute(args)

    mock_gateway.search_items.assert_called_once()
    query = mock_gateway.search_items.call_args[0][0]
    assert query.q == "Deep Learning"


def test_search_no_args(search_cmd, mock_gateway):
    args = argparse.Namespace(query=None, doi=None, title=None, limit=50, user=False)
    search_cmd.execute(args)
    mock_gateway.get_items_by_doi.assert_not_called()
    mock_gateway.search_items.assert_not_called()


def test_search_no_results(search_cmd, mock_gateway):
    args = argparse.Namespace(query="Nothing", doi=None, title=None, limit=50, user=False)
    mock_gateway.search_items.return_value = []
    search_cmd.execute(args)
    mock_gateway.search_items.assert_called_once()
