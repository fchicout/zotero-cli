from unittest.mock import MagicMock, patch

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
