import argparse
from unittest.mock import MagicMock, mock_open, patch

import pytest

from zotero_cli.cli.commands.item_cmd import ItemCommand


@pytest.fixture
def mock_clients():
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_zot_get,
        patch("zotero_cli.infra.factory.GatewayFactory.get_pdf_finder_service") as mock_pdf_get,
        patch("zotero_cli.infra.factory.GatewayFactory.get_attachment_service") as mock_att_get,
    ):
        yield {
            "gateway": mock_zot_get.return_value,
            "pdf_finder": mock_pdf_get.return_value,
            "attachment": mock_att_get.return_value,
        }


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")


def test_item_pdf_fetch_success(mock_clients, env_vars, capsys):
    mock_pdf = mock_clients["pdf_finder"]
    mock_pdf.enqueue_find_pdf.return_value = 123

    mock_job = MagicMock()
    mock_job.status = "COMPLETED"
    mock_pdf.job_queue.repo.get_job.return_value = mock_job

    args = MagicMock()
    args.verb = "pdf"
    args.pdf_verb = "fetch"
    args.key = "ITEM1"
    args.user = False

    # We patch asyncio.run to do nothing, but we must avoid recursion.
    # The real fix for unawaited coroutines in CLI tests is to NOT call main()
    # or ensure everything is synchronous.
    with patch("zotero_cli.cli.commands.item_cmd.asyncio.run"):
        ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "Starting resilient PDF discovery for 1 items" in out
    assert "Discovery workers finished" in out


def test_item_add_success(mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_item_template.return_value = {"itemType": "journalArticle", "creators": []}
    mock_gateway.create_generic_item.return_value = "NEWKEY123"

    args = MagicMock()
    args.verb = "add"
    args.collection = "MyCol"
    args.title = "New Paper"
    args.authors = "John Doe, Jane Smith"
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "Success!" in out
    assert "NEWKEY123" in out


def test_item_pdf_fetch_failure(mock_clients, env_vars, capsys):
    mock_pdf = mock_clients["pdf_finder"]
    mock_pdf.enqueue_find_pdf.return_value = 456

    mock_job = MagicMock()
    mock_job.status = "FAILED"
    mock_job.last_error = "404 Not Found"
    mock_pdf.job_queue.repo.get_job.return_value = mock_job

    args = MagicMock()
    args.verb = "pdf"
    args.pdf_verb = "fetch"
    args.key = "ITEM2"
    args.user = False

    with patch("zotero_cli.cli.commands.item_cmd.asyncio.run"):
        ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "Starting resilient PDF discovery for 1 items" in out
    assert "Discovery workers finished" in out


def test_item_inspect_success(mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    item = MagicMock()
    item.title = "Test Paper"
    item.item_type = "journalArticle"
    item.date = "2023"
    item.date_added = "2023-01-01"
    item.date_modified = "2023-01-02"
    item.authors = ["Author One", "Author Two"]
    item.doi = "10.1234/test"
    item.url = "http://test.com"
    item.abstract = "Test abstract."
    item.collections = ["COL1"]
    mock_gateway.get_item.return_value = item
    mock_gateway.get_item_children.return_value = []
    mock_gateway.get_collection.return_value = {"data": {"name": "My Collection"}}

    args = MagicMock()
    args.verb = "inspect"
    args.key = "TESTKEY123"
    args.raw = False
    args.format = None
    args.full_notes = False
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "Collections: My Collection (COL1)" in out
    assert "Test Paper" in out
    assert "TESTKEY123" in out
    assert "Added: 2023-01-01" in out
    assert "Modified: 2023-01-02" in out


def test_item_inspect_missing_key(mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    mock_gateway.get_item.return_value = None

    args = MagicMock()
    args.verb = "inspect"
    args.key = "MISSINGKEY"
    args.raw = False
    args.format = None
    args.full_notes = False
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "Item 'MISSINGKEY' not found" in out


def test_item_inspect_no_keys(mock_clients, env_vars, capsys):
    args = MagicMock()
    args.verb = "inspect"
    args.key = None
    args.file = None
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "Error: You must specify --key or --file" in out


def test_item_inspect_raw(mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    item = MagicMock()
    item.raw_data = {"key": "RAWKEY", "title": "Raw Paper"}
    mock_gateway.get_item.return_value = item

    args = MagicMock()
    args.verb = "inspect"
    args.key = "RAWKEY"
    args.raw = True
    args.format = None
    args.full_notes = False
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "RAWKEY" in out
    assert "Raw Paper" in out


@patch("zotero_cli.infra.factory.GatewayFactory.get_export_service")
def test_item_inspect_bibtex(mock_export, mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    item = MagicMock()
    mock_gateway.get_item.return_value = item
    mock_export.return_value.serialize_bibtex.return_value = "@article{bibtex}"

    args = MagicMock()
    args.verb = "inspect"
    args.key = "BIBKEY"
    args.raw = False
    args.format = "bibtex"
    args.full_notes = False
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "@article{bibtex}" in out


@patch("zotero_cli.infra.factory.GatewayFactory.get_export_service")
def test_item_inspect_ris(mock_export, mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    item = MagicMock()
    mock_gateway.get_item.return_value = item
    mock_export.return_value.serialize_ris.return_value = "TY  - JOUR\nER  - "

    args = MagicMock()
    args.verb = "inspect"
    args.key = "RISKEY"
    args.raw = False
    args.format = "ris"
    args.full_notes = False
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "TY  - JOUR" in out


@patch("builtins.open", new_callable=mock_open, read_data="KEY1\nKEY2\n")
def test_item_inspect_from_file(mock_file, mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    item1 = MagicMock()
    item1.title = "Paper 1"
    item1.item_type = "journalArticle"
    item1.abstract = "Abstract 1"
    item1.authors = []
    item1.collections = []

    item2 = MagicMock()
    item2.title = "Paper 2"
    item2.item_type = "journalArticle"
    item2.abstract = "Abstract 2"
    item2.authors = []
    item2.collections = []

    mock_gateway.get_item.side_effect = [item1, item2]

    args = MagicMock()
    args.verb = "inspect"
    args.key = None
    args.file = "keys.txt"
    args.raw = False
    args.format = None
    args.full_notes = False
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "Paper 1" in out
    assert "Paper 2" in out


def test_item_list_root(mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    item = MagicMock()
    item.key = "ROOTKEY123"
    item.title = "Root Paper"
    item.item_type = "journalArticle"
    mock_gateway.get_orphan_items.return_value = [item]

    args = MagicMock()
    args.verb = "list"
    args.root = True
    args.top_only = False
    args.trash = False
    args.collection = None
    args.user = False

    ItemCommand().execute(args)

    mock_gateway.get_orphan_items.assert_called_once_with(top_only=False)
    out = capsys.readouterr().out
    assert "Root/Orphan Items (unfiled)" in out
    assert "ROOTKEY123" in out
    assert "Root Paper" in out


def test_item_list_root_top_only(mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    item = MagicMock()
    item.key = "ROOTKEY123"
    item.title = "Root Paper"
    item.item_type = "journalArticle"
    mock_gateway.get_orphan_items.return_value = [item]

    args = MagicMock()
    args.verb = "list"
    args.root = True
    args.top_only = True
    args.trash = False
    args.collection = None
    args.user = False

    ItemCommand().execute(args)

    mock_gateway.get_orphan_items.assert_called_once_with(top_only=True)
    out = capsys.readouterr().out
    assert "Root/Orphan Items (unfiled)" in out
    assert "ROOTKEY123" in out
    assert "Root Paper" in out


def test_item_list_no_collection_or_root(mock_clients, env_vars, capsys):
    args = MagicMock()
    args.verb = "list"
    args.root = False
    args.trash = False
    args.collection = None
    args.user = False

    ItemCommand().execute(args)

    out = capsys.readouterr().out
    assert "Error: --collection or --root required for non-trash listings" in out


def test_item_delete_subparser_is_reachable():
    """Regression test for Issue #161: `delete` must have a registered
    subparser, not just an `execute()` dispatch branch - argparse's
    `required=True` subparser choice set otherwise rejects the command
    before `_handle_delete` is ever reached (same bug class as #146)."""
    parser = argparse.ArgumentParser()
    ItemCommand().register_args(parser)

    args = parser.parse_args(["delete", "--key", "ABCD1234"])

    assert args.verb == "delete"
    assert args.key == "ABCD1234"
    assert args.version is None


def test_item_delete_success(mock_clients, env_vars, capsys):
    gateway = mock_clients["gateway"]
    gateway.get_item.return_value = MagicMock(version=5)
    gateway.delete_item.return_value = True

    args = MagicMock()
    args.verb = "delete"
    args.key = "ABCD1234"
    args.version = None
    args.user = False

    ItemCommand().execute(args)

    gateway.delete_item.assert_called_once_with("ABCD1234", 5)
    assert "Deleted item ABCD1234 successfully." in capsys.readouterr().out


def test_item_delete_missing_item(mock_clients, env_vars, capsys):
    gateway = mock_clients["gateway"]
    gateway.get_item.return_value = None

    args = MagicMock()
    args.verb = "delete"
    args.key = "MISSING"
    args.version = None
    args.user = False

    ItemCommand().execute(args)

    gateway.delete_item.assert_not_called()
    assert "Error: Item MISSING not found." in capsys.readouterr().out


def test_item_trash_subparser_is_reachable():
    """Regression test for Issue #145: `trash`/`restore` must have registered
    subparsers, not just execute() dispatch branches (same bug class as
    #146/#161)."""
    parser = argparse.ArgumentParser()
    ItemCommand().register_args(parser)

    args = parser.parse_args(["trash", "--key", "ABCD1234", "--execute", "--force"])
    assert args.verb == "trash"
    assert args.key == "ABCD1234"
    assert args.execute is True
    assert args.force is True


def test_item_restore_subparser_is_reachable():
    parser = argparse.ArgumentParser()
    ItemCommand().register_args(parser)

    args = parser.parse_args(["restore", "--key", "ABCD1234"])
    assert args.verb == "restore"
    assert args.key == "ABCD1234"
    assert args.execute is False
    assert args.force is False


def test_item_trash_online_mode_rejected(env_vars, capsys):
    from zotero_cli.infra.zotero_api import ZoteroAPIClient

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        gateway = MagicMock(spec=ZoteroAPIClient)
        mock_get.return_value = gateway

        args = MagicMock()
        args.verb = "trash"
        args.key = "ABCD1234"
        args.execute = True
        args.force = True
        args.user = False

        ItemCommand().execute(args)

    # ZoteroAPIClient (the online gateway) has no trash_item/restore_item
    # method at all -- calling one would raise AttributeError on this
    # spec'd mock, so a clean rejection message (and no such call) is the
    # only possible correct outcome here.
    assert "only supports --offline mode" in capsys.readouterr().out


def test_item_restore_online_mode_rejected(env_vars, capsys):
    from zotero_cli.infra.zotero_api import ZoteroAPIClient

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        gateway = MagicMock(spec=ZoteroAPIClient)
        mock_get.return_value = gateway

        args = MagicMock()
        args.verb = "restore"
        args.key = "ABCD1234"
        args.execute = True
        args.force = True
        args.user = False

        ItemCommand().execute(args)

    assert "only supports --offline mode" in capsys.readouterr().out


def test_item_trash_preview_only_without_execute(env_vars, capsys):
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        gateway = MagicMock(spec=SqliteZoteroGateway)
        gateway.get_item.return_value = MagicMock(title="Some Paper")
        mock_get.return_value = gateway

        args = MagicMock()
        args.verb = "trash"
        args.key = "ABCD1234"
        args.execute = False
        args.force = False
        args.user = False

        ItemCommand().execute(args)

    gateway.trash_item.assert_not_called()
    assert "Preview only" in capsys.readouterr().out


def test_item_trash_missing_item(env_vars, capsys):
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        gateway = MagicMock(spec=SqliteZoteroGateway)
        gateway.get_item.return_value = None
        mock_get.return_value = gateway

        args = MagicMock()
        args.verb = "trash"
        args.key = "MISSING"
        args.execute = True
        args.force = True
        args.user = False

        ItemCommand().execute(args)

    gateway.trash_item.assert_not_called()
    assert "not found" in capsys.readouterr().out


def test_item_trash_execute_force_writes(env_vars, capsys):
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        gateway = MagicMock(spec=SqliteZoteroGateway)
        gateway.get_item.return_value = MagicMock(title="Some Paper")
        gateway.trash_item.return_value = True
        mock_get.return_value = gateway

        args = MagicMock()
        args.verb = "trash"
        args.key = "ABCD1234"
        args.execute = True
        args.force = True
        args.user = False

        ItemCommand().execute(args)

    gateway.trash_item.assert_called_once_with("ABCD1234")
    assert "Moved to trash" in capsys.readouterr().out


def test_item_restore_execute_force_writes(env_vars, capsys):
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        gateway = MagicMock(spec=SqliteZoteroGateway)
        gateway.get_item.return_value = MagicMock(title="Some Paper")
        gateway.restore_item.return_value = True
        mock_get.return_value = gateway

        args = MagicMock()
        args.verb = "restore"
        args.key = "ABCD1234"
        args.execute = True
        args.force = True
        args.user = False

        ItemCommand().execute(args)

    gateway.restore_item.assert_called_once_with("ABCD1234")
    assert "Restored from trash" in capsys.readouterr().out


def test_item_trash_execute_without_force_prompts_and_aborts(env_vars, capsys):
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get,
        patch("rich.prompt.Confirm.ask", return_value=False) as mock_confirm,
    ):
        gateway = MagicMock(spec=SqliteZoteroGateway)
        gateway.get_item.return_value = MagicMock(title="Some Paper")
        mock_get.return_value = gateway

        args = MagicMock()
        args.verb = "trash"
        args.key = "ABCD1234"
        args.execute = True
        args.force = False
        args.user = False

        ItemCommand().execute(args)

    mock_confirm.assert_called_once()
    gateway.trash_item.assert_not_called()
    assert "Aborted" in capsys.readouterr().out
