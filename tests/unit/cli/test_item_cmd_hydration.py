import argparse
from unittest.mock import Mock, patch

import pytest

from zotero_cli.cli.commands.item_cmd import ItemCommand


@pytest.fixture
def item_cmd():
    return ItemCommand()


@patch("zotero_cli.infra.factory.GatewayFactory.get_enrichment_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
def test_item_hydrate_dispatch_key(mock_gateway, mock_enrichment, item_cmd):
    # Setup
    mock_service = Mock()
    mock_enrichment.return_value = mock_service
    mock_service.hydrate_item.return_value = {
        "key": "K1",
        "title": "T1",
        "old_doi": "N/A",
        "new_doi": "DOI1",
        "new_journal": "J1",
    }

    args = argparse.Namespace(
        verb="hydrate", key="K1", collection=None, all=False, dry_run=False, user=False
    )

    # Execute
    item_cmd.execute(args)

    # Assert
    mock_service.hydrate_item.assert_called_once_with("K1", dry_run=False)


@patch("zotero_cli.infra.factory.GatewayFactory.get_enrichment_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway")
def test_item_hydrate_dispatch_collection(mock_gateway, mock_enrichment, item_cmd):
    # Setup
    mock_service = Mock()
    mock_enrichment.return_value = mock_service
    mock_service.hydrate_collection.return_value = []

    args = argparse.Namespace(
        verb="hydrate", key=None, collection="MyCol", all=False, dry_run=True, user=False
    )

    # Execute
    item_cmd.execute(args)

    # Assert
    mock_service.hydrate_collection.assert_called_once_with("MyCol", dry_run=True)
