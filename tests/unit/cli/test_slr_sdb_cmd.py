import sys
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.main import main


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def mock_sdb_service():
    with patch("zotero_cli.core.services.sdb.sdb_service.SDBService") as mock_cls:
        mock_instance = mock_cls.return_value
        yield mock_instance


def test_slr_sdb_inspect(mock_gateway, mock_sdb_service, capsys):
    mock_sdb_service.inspect_item_sdb.return_value = [
        {"decision": "accepted", "reason_code": ["C1"], "persona": "P1", "phase": "ph1"}
    ]

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
    ):
        test_args = ["zotero-cli", "slr", "sdb", "inspect", "KEY1"]
        with patch.object(sys, "argv", test_args):
            main()

    mock_sdb_service.inspect_item_sdb.assert_called_with("KEY1")
    mock_sdb_service.build_inspect_table.assert_called_once()


def test_slr_sdb_edit_dry_run(mock_gateway, mock_sdb_service, capsys):
    mock_sdb_service.edit_sdb_entry.return_value = (True, "Would update")

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
    ):
        test_args = [
            "zotero-cli",
            "slr",
            "sdb",
            "edit",
            "KEY1",
            "--persona",
            "P1",
            "--phase",
            "ph1",
            "--set-decision",
            "rejected",
        ]
        with patch.object(sys, "argv", test_args):
            main()

    # Verify service call with dry_run=True (default)
    mock_sdb_service.edit_sdb_entry.assert_called_with(
        "KEY1", "P1", "ph1", {"decision": "rejected"}, dry_run=True
    )
    assert "Would update" in capsys.readouterr().out


def test_slr_sdb_upgrade(mock_gateway, mock_sdb_service, capsys):
    mock_sdb_service.upgrade_sdb_entries.return_value = {
        "scanned": 1,
        "upgraded": 1,
        "skipped": 0,
        "errors": 0,
    }

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
    ):
        test_args = ["zotero-cli", "slr", "sdb", "upgrade", "--collection", "Col1", "--execute"]
        with patch.object(sys, "argv", test_args):
            main()

    mock_sdb_service.upgrade_sdb_entries.assert_called_with("Col1", dry_run=False)
    assert "Upgraded: 1" in capsys.readouterr().out


def test_slr_sdb_inspect_empty(mock_gateway, mock_sdb_service, capsys):
    mock_sdb_service.inspect_item_sdb.return_value = []

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
    ):
        test_args = ["zotero-cli", "slr", "sdb", "inspect", "KEY1"]
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "No SDB entries found for KEY1" in out


def test_slr_sdb_upgrade_dry_run(mock_gateway, mock_sdb_service, capsys):
    mock_sdb_service.upgrade_sdb_entries.return_value = {
        "scanned": 1,
        "upgraded": 0,
        "skipped": 1,
        "errors": 0,
    }

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
    ):
        test_args = ["zotero-cli", "slr", "sdb", "upgrade", "--collection", "Col1"]
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Running SDB Upgrade in DRY-RUN mode" in out
    assert "Scanned: 1" in out


def test_slr_sdb_export(mock_gateway, capsys):
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
    ), patch("zotero_cli.core.services.sync_service.SyncService") as mock_sync_cls:
        sync_inst = mock_sync_cls.return_value
        sync_inst.recover_state_from_notes.return_value = True

        test_args = ["zotero-cli", "slr", "sdb", "export", "--collection", "Col1", "--output", "out.csv"]
        with patch.object(sys, "argv", test_args):
            main()

        sync_inst.recover_state_from_notes.assert_called_once()
        out = capsys.readouterr().out
        assert "Syncing local CSV from 'Col1' notes..." in out


def test_slr_sdb_reset_dry_run(mock_gateway, capsys):
    item = MagicMock()
    item.key = "I1"
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_items_in_collection.return_value = [item]

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway
    ), patch("zotero_cli.core.services.purge_service.PurgeService") as mock_purge_cls:
        purge_inst = mock_purge_cls.return_value
        purge_inst.purge_notes.return_value = {"deleted": 2}
        purge_inst.purge_tags.return_value = {"deleted": 1}

        test_args = ["zotero-cli", "slr", "sdb", "reset", "--name", "Col1", "--phase", "title_abstract", "--force"]
        with patch.object(sys, "argv", test_args):
            main()

        purge_inst.purge_notes.assert_called_once()
        purge_inst.purge_tags.assert_called_once()
        out = capsys.readouterr().out
        assert "Reset results for 'Col1'" in out
        assert "Reset complete." in out

