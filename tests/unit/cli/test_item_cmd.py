import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_cli.cli.main import main


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


@pytest.mark.anyio
async def test_item_pdf_fetch_success(mock_clients, env_vars, capsys):
    mock_pdf = mock_clients["pdf_finder"]
    mock_pdf.enqueue_find_pdf.return_value = 123
    mock_pdf.process_jobs = AsyncMock()

    # Mock repo to return completed job
    mock_job = MagicMock()
    mock_job.status = "COMPLETED"
    mock_pdf.job_queue.repo.get_job.return_value = mock_job

    test_args = ["zotero-cli", "item", "pdf", "fetch", "--key", "ITEM1"]
    with patch("zotero_cli.cli.commands.item_cmd.asyncio.run") as _:
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Starting resilient PDF discovery for 1 items" in out
    assert "Discovery workers finished" in out


def test_item_add_success(mock_clients, env_vars, capsys):
    mock_gateway = mock_clients["gateway"]
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_item_template.return_value = {"itemType": "journalArticle", "creators": []}
    mock_gateway.create_generic_item.return_value = "NEWKEY123"

    test_args = [
        "zotero-cli",
        "item",
        "add",
        "--collection",
        "MyCol",
        "--title",
        "New Paper",
        "--authors",
        "John Doe, Jane Smith",
    ]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "Success!" in out
    assert "NEWKEY123" in out
    mock_gateway.get_item_template.assert_called_with("journalArticle")
    mock_gateway.create_generic_item.assert_called_once()
    payload = mock_gateway.create_generic_item.call_args[0][0]
    assert payload["title"] == "New Paper"
    assert payload["collections"] == ["COL1"]
    assert len(payload["creators"]) == 2
    assert payload["creators"][0]["lastName"] == "Doe"


@pytest.mark.anyio
async def test_item_pdf_fetch_failure(mock_clients, env_vars, capsys):
    mock_pdf = mock_clients["pdf_finder"]
    mock_pdf.enqueue_find_pdf.return_value = 456
    mock_pdf.process_jobs = AsyncMock()

    mock_job = MagicMock()
    mock_job.status = "FAILED"
    mock_job.last_error = "404 Not Found"
    mock_pdf.job_queue.repo.get_job.return_value = mock_job

    test_args = ["zotero-cli", "item", "pdf", "fetch", "--key", "ITEM2"]
    with patch("zotero_cli.cli.commands.item_cmd.asyncio.run"):
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Starting resilient PDF discovery for 1 items" in out
    assert "Discovery workers finished" in out
