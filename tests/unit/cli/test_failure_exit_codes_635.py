"""A failed export or backup must fail the command (Issue #635), not print and exit 0."""

import argparse
from typing import Any
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.collection_cmd import CollectionCommand
from zotero_cli.cli.commands.item_cmd import ItemCommand
from zotero_cli.cli.commands.system_cmd import SystemCommand
from zotero_cli.core.exceptions import ZoteroCliError
from zotero_cli.core.zotero_item import ZoteroItem


def test_a_failed_item_metadata_export_is_an_error() -> None:
    item = ZoteroItem(key="K1", version=1, item_type="journalArticle")
    args = argparse.Namespace(
        verb="export",
        key="K1",
        export_format="bibtex",
        output="out.bib",
        annotations=False,
        style="apa",
        render="plain",
        user=False,
    )
    command = ItemCommand()
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as get_gateway,
        patch("zotero_cli.infra.factory.GatewayFactory.get_export_service") as get_export,
    ):
        get_gateway.return_value.get_item.return_value = item
        get_export.return_value.export_items.return_value = False

        with pytest.raises(ZoteroCliError, match="Export failed") as raised:
            command.execute(args)

    assert raised.value.exit_code == 1


def test_a_failed_collection_backup_is_an_error(mock_gateway: Any) -> None:
    gateway = mock_gateway
    gateway.get_collection_id_by_name.return_value = "COL"
    gateway.get_collection.return_value = {"meta": {"numItems": 1}}
    args = argparse.Namespace(verb="backup", collection="COL", output="b.zaf", user=False)
    command = CollectionCommand()
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway),
        patch("zotero_cli.infra.factory.GatewayFactory.get_backup_service") as get_backup,
    ):
        get_backup.return_value.backup_collection.side_effect = OSError("disk full")

        with pytest.raises(ZoteroCliError, match="Backup failed: disk full") as raised:
            command.execute(args)

    assert raised.value.exit_code == 1


def test_a_failed_system_backup_is_an_error() -> None:
    args = argparse.Namespace(verb="backup", output="b.zaf", user=False)
    command = SystemCommand()
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_backup_service") as get_backup,
    ):
        get_backup.return_value.backup_system.side_effect = OSError("disk full")

        with pytest.raises(ZoteroCliError, match="Backup failed: disk full") as raised:
            command.execute(args)

    assert raised.value.exit_code == 1
