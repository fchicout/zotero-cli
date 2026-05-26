import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.collection_cmd import CollectionCommand


@pytest.fixture
def mock_gateway():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        gateway = MagicMock()
        mock_get.return_value = gateway
        yield gateway


@pytest.fixture
def mock_collection_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service") as mock_get:
        service = MagicMock()
        mock_get.return_value = service
        yield service


@pytest.fixture
def mock_purge_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_purge_service") as mock_get:
        service = MagicMock()
        mock_get.return_value = service
        yield service


@pytest.fixture
def mock_export_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_export_service") as mock_get:
        service = MagicMock()
        mock_get.return_value = service
        yield service


@pytest.fixture
def mock_attachment_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_attachment_service") as mock_get:
        service = MagicMock()
        mock_get.return_value = service
        yield service


def test_register_args():
    parser = argparse.ArgumentParser()
    CollectionCommand().register_args(parser)
    actions = parser._actions
    assert len(actions) > 0


def test_collection_list_table(mock_gateway, capsys):
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "Col 1", "parentCollection": None}, "meta": {"numItems": 5}}
    ]

    args = argparse.Namespace(verb="list", table=True, user=False)
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Col 1" in out
    assert "C1" in out
    assert "5" in out


def test_collection_list_tree(mock_gateway, capsys):
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "Col 1", "parentCollection": None}, "meta": {"numItems": 5}},
        {"key": "C2", "data": {"name": "Sub Col", "parentCollection": "C1"}, "meta": {"numItems": 2}}
    ]

    args = argparse.Namespace(verb="list", table=False, user=False)
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Col 1" in out
    assert "Sub Col" in out


def test_collection_create_success(mock_gateway, capsys):
    mock_gateway.get_collection_id_by_name.return_value = "P123"
    mock_gateway.create_collection.return_value = "NEW_KEY"

    args = argparse.Namespace(verb="create", name="New Col", parent="Parent Col", user=False)
    CollectionCommand().execute(args)

    mock_gateway.get_collection_id_by_name.assert_called_with("Parent Col")
    mock_gateway.create_collection.assert_called_with("New Col", parent_key="P123")
    out = capsys.readouterr().out
    assert "Created collection 'New Col' (Key: NEW_KEY)" in out


def test_collection_create_fail(mock_gateway, capsys):
    mock_gateway.get_collection_id_by_name.return_value = None
    mock_gateway.create_collection.return_value = None

    args = argparse.Namespace(verb="create", name="New Col", parent=None, user=False)
    CollectionCommand().execute(args)

    mock_gateway.create_collection.assert_called_with("New Col", parent_key=None)
    out = capsys.readouterr().out
    assert "Failed to create collection." in out


def test_collection_delete_success(mock_gateway, mock_collection_service, capsys):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.get_collection.return_value = {"version": 42}
    mock_collection_service.delete_collection.return_value = True

    args = argparse.Namespace(verb="delete", key="COL_KEY", version=None, recursive=True, user=False)
    CollectionCommand().execute(args)

    mock_collection_service.delete_collection.assert_called_with("COL_KEY", 42, recursive=True)
    out = capsys.readouterr().out
    assert "Deleted collection 'COL_KEY'" in out


def test_collection_delete_not_found(mock_gateway, mock_collection_service, capsys):
    mock_gateway.get_collection_id_by_name.return_value = None
    mock_gateway.get_collection.return_value = None

    args = argparse.Namespace(verb="delete", key="INVALID_KEY", version=None, recursive=False, user=False)
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Collection 'INVALID_KEY' not found." in out


def test_collection_rename_success(mock_gateway, capsys):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.rename_collection.return_value = True

    args = argparse.Namespace(verb="rename", key="COL_KEY", name="New Name", version=100, user=False)
    CollectionCommand().execute(args)

    mock_gateway.rename_collection.assert_called_with("COL_KEY", 100, "New Name")
    out = capsys.readouterr().out
    assert "Renamed collection to 'New Name'" in out


def test_collection_rename_fail(mock_gateway, capsys):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.rename_collection.return_value = False

    args = argparse.Namespace(verb="rename", key="COL_KEY", name="New Name", version=100, user=False)
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Failed to rename collection." in out


def test_collection_clean(mock_collection_service, capsys):
    mock_collection_service.empty_collection.return_value = 15

    args = argparse.Namespace(verb="clean", collection="COL_KEY", verbose=True, user=False)
    CollectionCommand().execute(args)

    mock_collection_service.empty_collection.assert_called_with("COL_KEY", True)
    out = capsys.readouterr().out
    assert "Deleted 15 items from 'COL_KEY'" in out


def test_collection_backup_success(mock_gateway, capsys):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.get_collection.return_value = {"meta": {"numItems": 3}}

    args = argparse.Namespace(verb="backup", name="COL_KEY", output="backup.zaf", user=False)
    with patch("zotero_cli.cli.commands.collection_cmd.BackupService") as mock_backup_srv:
        service_inst = MagicMock()
        mock_backup_srv.return_value = service_inst
        CollectionCommand().execute(args)
        service_inst.backup_collection.assert_called_once()

    out = capsys.readouterr().out
    assert "Starting Backup for Collection" in out
    assert "Backup complete" in out


def test_collection_backup_not_found(mock_gateway, capsys):
    mock_gateway.get_collection_id_by_name.return_value = None
    mock_gateway.get_collection.return_value = None

    args = argparse.Namespace(verb="backup", name="COL_KEY", output="backup.zaf", user=False)
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Collection 'COL_KEY' not found." in out


def test_collection_export_metadata_success(mock_export_service, capsys):
    mock_export_service.export_collection.return_value = True

    args = argparse.Namespace(verb="export", name="COL_KEY", format="bibtex", output="out.bib", user=False)
    CollectionCommand().execute(args)

    mock_export_service.export_collection.assert_called_with("COL_KEY", "out.bib", "bibtex")
    out = capsys.readouterr().out
    assert "Export complete" in out


def test_collection_export_metadata_fail(mock_export_service, capsys):
    mock_export_service.export_collection.return_value = False

    args = argparse.Namespace(verb="export", name="COL_KEY", format="ris", output="out.ris", user=False)
    with pytest.raises(SystemExit):
        CollectionCommand().execute(args)


def test_collection_export_markdown_success(mock_gateway, mock_attachment_service, capsys):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.get_collection.return_value = {"key": "COL_KEY"}
    item1 = MagicMock()
    item1.key = "I1"
    item2 = MagicMock()
    item2.key = "I2"
    mock_gateway.get_items_in_collection.return_value = [item1, item2]

    mock_attachment_service._export_item_markdown.side_effect = ["success", "skipped"]

    args = argparse.Namespace(verb="export", name="COL_KEY", format="md", output="md_dir", user=False)
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Export Summary" in out
    assert "Success: 1" in out
    assert "Skipped (No PDF): 1" in out


def test_collection_purge_success(mock_purge_service, capsys):
    mock_purge_service.purge_collection_assets.return_value = {"deleted": 12, "errors": 0}

    args = argparse.Namespace(
        verb="purge",
        name="COL_KEY",
        files=True,
        notes=True,
        tags=False,
        force=True,
        recursive=True,
        user=False
    )
    CollectionCommand().execute(args)

    mock_purge_service.purge_collection_assets.assert_called_with(
        "COL_KEY", types=["files", "notes"], recursive=True, dry_run=False
    )
    out = capsys.readouterr().out
    assert "Purge Complete" in out
    assert "Deleted: 12" in out
