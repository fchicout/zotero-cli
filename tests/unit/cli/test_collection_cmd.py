import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.collection_cmd import CollectionCommand
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        gateway = MagicMock()
        mock_get.return_value = gateway
        yield gateway


@pytest.fixture
def mock_collection_service(mock_gateway):
    # CollectionCommand.execute() unconditionally constructs a real gateway
    # up front regardless of verb - depends on mock_gateway (rather than
    # separately re-patching get_zotero_gateway itself) so a test
    # requesting both fixtures together still gets exactly one patch on
    # that target, not two competing ones.
    with patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service") as mock_get:
        service = MagicMock()
        mock_get.return_value = service
        yield service


@pytest.fixture
def mock_purge_service(mock_gateway):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_purge_service") as mock_get:
        service = MagicMock()
        mock_get.return_value = service
        yield service


@pytest.fixture
def mock_export_service(mock_gateway):
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
        {
            "key": "C2",
            "data": {"name": "Sub Col", "parentCollection": "C1"},
            "meta": {"numItems": 2},
        },
    ]

    args = argparse.Namespace(verb="list", table=False, user=False)
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Col 1" in out
    assert "Sub Col" in out


@pytest.mark.parametrize("table", [False, True])
def test_collection_list_tolerates_missing_meta(mock_gateway, capsys, table):
    """Issue #322: a gateway returning collections without the Web API's
    `meta` envelope must not crash `collection list` - item count falls
    back to 0 in both tree and --table modes."""
    mock_gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "Col 1", "parentCollection": None}},
        {"key": "C2", "data": {"name": "Sub Col", "parentCollection": "C1"}, "meta": None},
    ]

    CollectionCommand().execute(argparse.Namespace(verb="list", table=table, user=False))

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


def _delete_args(**kw):
    base = dict(
        verb="delete",
        key="COL_KEY",
        version=None,
        recursive=False,
        execute=False,
        yes=False,
        include_shared=False,
        user=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def _recursive_plan():
    from zotero_cli.core.services.collection_service import RecursiveDeletePlan

    only_here = ZoteroItem(key="I1", version=1, item_type="journalArticle", title="Only here")
    shared = ZoteroItem(key="I2", version=1, item_type="journalArticle", title="Also elsewhere")
    return RecursiveDeletePlan(
        root_key="COL_KEY",
        collections=[("SUB", 1, "Sub"), ("COL_KEY", 42, "Root")],
        items_to_delete=[only_here],
        shared_items=[shared],
    )


def test_collection_delete_non_recursive_keeps_items(
    mock_gateway, mock_collection_service, capsys
):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.get_collection.return_value = {"version": 42}
    mock_collection_service.delete_collection.return_value = True

    CollectionCommand().execute(_delete_args())

    mock_collection_service.delete_collection.assert_called_with("COL_KEY", 42)
    assert "Its items stay in your library" in capsys.readouterr().out


def test_collection_delete_recursive_previews_by_default(
    mock_gateway, mock_collection_service, capsys
):
    """Issue #378: a recursive delete used to run with no preview or prompt."""
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.get_collection.return_value = {"version": 42}
    mock_collection_service.plan_recursive_delete.return_value = _recursive_plan()

    CollectionCommand().execute(_delete_args(recursive=True))

    mock_collection_service.plan_recursive_delete.assert_called_with("COL_KEY", 42)
    mock_collection_service.execute_recursive_delete.assert_not_called()
    out = capsys.readouterr().out
    assert "2 collection(s)" in out and "1 item(s) filed only inside" in out
    assert "will be kept" in out and "--execute" in out


def test_collection_delete_recursive_refuses_without_a_terminal_or_yes(
    mock_gateway, mock_collection_service, capsys, monkeypatch
):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.get_collection.return_value = {"version": 42}
    mock_collection_service.plan_recursive_delete.return_value = _recursive_plan()
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    with pytest.raises(SystemExit) as exc:
        CollectionCommand().execute(_delete_args(recursive=True, execute=True))

    assert exc.value.code == 2
    mock_collection_service.execute_recursive_delete.assert_not_called()
    assert "--yes" in capsys.readouterr().err


def test_collection_delete_recursive_executes_with_yes(
    mock_gateway, mock_collection_service, capsys
):
    from zotero_cli.core.services.collection_service import RecursiveDeleteResult

    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.get_collection.return_value = {"version": 42}
    plan = _recursive_plan()
    mock_collection_service.plan_recursive_delete.return_value = plan
    mock_collection_service.execute_recursive_delete.return_value = RecursiveDeleteResult(
        deleted_items=1, deleted_collections=2
    )

    CollectionCommand().execute(_delete_args(recursive=True, execute=True, yes=True))

    mock_collection_service.execute_recursive_delete.assert_called_once_with(
        plan, include_shared=False
    )
    assert "Deleted 1 item(s) and 2 collection(s)" in capsys.readouterr().out


def test_collection_delete_not_found(mock_gateway, mock_collection_service, capsys):
    mock_gateway.get_collection_id_by_name.return_value = None
    mock_gateway.get_collection.return_value = None

    args = argparse.Namespace(
        verb="delete", key="INVALID_KEY", version=None, recursive=False, user=False
    )
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Collection 'INVALID_KEY' not found." in out


def test_collection_rename_success(mock_gateway, capsys):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.rename_collection.return_value = True

    args = argparse.Namespace(
        verb="rename", key="COL_KEY", name="New Name", version=100, user=False
    )
    CollectionCommand().execute(args)

    mock_gateway.rename_collection.assert_called_with("COL_KEY", 100, "New Name")
    out = capsys.readouterr().out
    assert "Renamed collection to 'New Name'" in out


def test_collection_rename_fail(mock_gateway, capsys):
    mock_gateway.get_collection_id_by_name.return_value = "COL_KEY"
    mock_gateway.rename_collection.return_value = False

    args = argparse.Namespace(
        verb="rename", key="COL_KEY", name="New Name", version=100, user=False
    )
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Failed to rename collection." in out


def _clean_plan():
    from zotero_cli.core.services.collection_service import CollectionRemovalPlan

    return CollectionRemovalPlan(
        "COL_KEY",
        [
            ZoteroItem(key="I1", version=1, item_type="journalArticle", collections=["COL_KEY"]),
            ZoteroItem(
                key="I2", version=1, item_type="journalArticle", collections=["COL_KEY", "OTHER"]
            ),
        ],
    )


def test_collection_clean_previews_and_never_deletes(mock_collection_service, capsys):
    """Issue #364: clean used to hard-delete every item in the collection."""
    mock_collection_service.plan_clean.return_value = _clean_plan()

    args = argparse.Namespace(
        verb="clean", collection="COL_KEY", verbose=False, execute=False, user=False
    )
    CollectionCommand().execute(args)

    mock_collection_service.remove_from_collection.assert_not_called()
    mock_collection_service.delete_collection.assert_not_called()
    out = " ".join(capsys.readouterr().out.split())
    assert "2 item(s) will be removed" in out
    assert "1 of them are in no other collection" in out
    assert "--execute" in out


def test_collection_clean_execute_removes_from_collection(mock_collection_service, capsys):
    plan = _clean_plan()
    mock_collection_service.plan_clean.return_value = plan
    mock_collection_service.remove_from_collection.return_value = (2, [])

    args = argparse.Namespace(
        verb="clean", collection="COL_KEY", verbose=False, execute=True, user=False
    )
    CollectionCommand().execute(args)

    mock_collection_service.remove_from_collection.assert_called_once_with(plan)
    assert "Removed 2 item(s)" in capsys.readouterr().out


def test_collection_clean_unknown_collection_exits_non_zero(mock_collection_service, capsys):
    mock_collection_service.plan_clean.return_value = None
    args = argparse.Namespace(verb="clean", collection="Nope", verbose=False, execute=True, user=False)
    with pytest.raises(SystemExit) as exc:
        CollectionCommand().execute(args)
    assert exc.value.code == 1
    assert "not found" in capsys.readouterr().err


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


def test_collection_backup_not_found_bracketed_name_renders_literally(mock_gateway, capsys):
    """Issue #253: a collection name containing a bracketed substring
    must not be silently consumed/reinterpreted as Rich markup - it must
    render as literal text."""
    mock_gateway.get_collection_id_by_name.return_value = None
    mock_gateway.get_collection.return_value = None

    args = argparse.Namespace(
        verb="backup", name="[Archived] Old Project", output="backup.zaf", user=False
    )
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Collection '[Archived] Old Project' not found." in out


def test_collection_export_metadata_success(mock_export_service, capsys):
    mock_export_service.export_collection.return_value = True

    args = argparse.Namespace(
        verb="export", name="COL_KEY", format="bibtex", output="out.bib", user=False
    )
    CollectionCommand().execute(args)

    mock_export_service.export_collection.assert_called_with("COL_KEY", "out.bib", "bibtex")
    out = capsys.readouterr().out
    assert "Export complete" in out


def test_collection_export_metadata_fail(mock_export_service, capsys):
    mock_export_service.export_collection.return_value = False

    args = argparse.Namespace(
        verb="export", name="COL_KEY", format="ris", output="out.ris", user=False
    )
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

    args = argparse.Namespace(
        verb="export", name="COL_KEY", format="md", output="md_dir", user=False
    )
    CollectionCommand().execute(args)

    out = capsys.readouterr().out
    assert "Export Summary" in out
    assert "Success: 1" in out
    assert "Skipped (No PDF): 1" in out


def test_collection_purge_subparser_is_reachable():
    """Regression test for Issue #146: `purge` must have a registered
    subparser, not just an `execute()` dispatch branch - argparse's
    `required=True` subparser choice set otherwise rejects the command
    before `_handle_purge` is ever reached (same bug class as #161)."""
    parser = argparse.ArgumentParser()
    CollectionCommand().register_args(parser)

    args = parser.parse_args(
        ["purge", "--name", "COL_KEY", "--files", "--notes", "--recursive", "--force"]
    )

    assert args.verb == "purge"
    assert args.name == "COL_KEY"
    assert args.files is True
    assert args.notes is True
    assert args.tags is False
    assert args.recursive is True
    assert args.force is True


def test_collection_purge_no_asset_types_aborts(mock_purge_service, capsys):
    args = argparse.Namespace(
        verb="purge",
        name="COL_KEY",
        files=False,
        notes=False,
        tags=False,
        force=True,
        recursive=False,
        user=False,
    )
    CollectionCommand().execute(args)

    mock_purge_service.purge_collection_assets.assert_not_called()
    assert "Specify what to purge" in capsys.readouterr().out


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
        user=False,
    )
    CollectionCommand().execute(args)

    mock_purge_service.purge_collection_assets.assert_called_with(
        "COL_KEY", types=["files", "notes"], recursive=True, dry_run=False
    )
    out = capsys.readouterr().out
    assert "Purge Complete" in out
    assert "Deleted: 12" in out
