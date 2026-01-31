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
            "attachment": mock_att_get.return_value
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

    test_args = ["zotero-cli", "item", "pdf", "fetch", "ITEM1"]
    with patch("zotero_cli.cli.commands.item_cmd.asyncio.run") as mock_run:
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Enqueued discovery job 123" in out
    assert "Successfully attached PDF" in out
    mock_pdf.enqueue_find_pdf.assert_called_with("ITEM1")
    mock_run.assert_called_once()


@pytest.mark.anyio
async def test_item_pdf_fetch_failure(mock_clients, env_vars, capsys):
    mock_pdf = mock_clients["pdf_finder"]
    mock_pdf.enqueue_find_pdf.return_value = 456
    mock_pdf.process_jobs = AsyncMock()

    mock_job = MagicMock()
    mock_job.status = "FAILED"
    mock_job.last_error = "404 Not Found"
    mock_pdf.job_queue.repo.get_job.return_value = mock_job

    test_args = ["zotero-cli", "item", "pdf", "fetch", "ITEM2"]
    with patch("zotero_cli.cli.commands.item_cmd.asyncio.run"):
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Failed to attach PDF" in out
    assert "404 Not Found" in out

