from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_cli.core.models import Job
from zotero_cli.core.services.pdf_finder_service import PDFFinderService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_job_queue():
    return MagicMock()


@pytest.fixture
def mock_item_repo():
    return MagicMock()


@pytest.fixture
def mock_attachment_repo():
    return MagicMock()


@pytest.fixture
def mock_resolver():
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    return resolver


@pytest.fixture
def finder_service(mock_job_queue, mock_item_repo, mock_attachment_repo, mock_resolver):
    return PDFFinderService(mock_job_queue, mock_item_repo, mock_attachment_repo, [mock_resolver])


@pytest.mark.anyio
async def test_process_job_success(
    finder_service, mock_item_repo, mock_attachment_repo, mock_resolver, mock_job_queue
):
    # Setup
    item_key = "ABC123"
    job = Job(id=1, item_key=item_key, task_type="fetch_pdf", payload={})

    mock_item = ZoteroItem(key=item_key, version=1, item_type="journalArticle")
    mock_item_repo.get_item.return_value = mock_item

    # Resolver returns a temp file
    dummy_pdf = Path("test.pdf")
    dummy_pdf.write_bytes(b"%PDF-1.4")
    mock_resolver.resolve.return_value = dummy_pdf

    mock_attachment_repo.upload_attachment.return_value = True

    # Execute
    await finder_service._process_job(job)

    # Verify
    mock_attachment_repo.upload_attachment.assert_called_once_with(
        item_key, str(dummy_pdf), mime_type="application/pdf"
    )
    mock_job_queue.complete_job.assert_called_once()
    assert not dummy_pdf.exists()  # Should be cleaned up


@pytest.mark.anyio
async def test_process_job_no_resolver_found(
    finder_service, mock_item_repo, mock_resolver, mock_job_queue
):
    item_key = "DEF456"
    job = Job(id=2, item_key=item_key, task_type="fetch_pdf", payload={})

    mock_item = ZoteroItem(key=item_key, version=1, item_type="journalArticle")
    mock_item_repo.get_item.return_value = mock_item

    mock_resolver.resolve.return_value = None

    await finder_service._process_job(job)

    mock_job_queue.fail_job.assert_called_once_with(
        2, "No PDF found (All resolvers returned None)", retry=True
    )


@pytest.mark.anyio
async def test_process_job_item_not_found(finder_service, mock_item_repo, mock_job_queue):
    job = Job(id=3, item_key="MISSING", task_type="fetch_pdf", payload={})
    mock_item_repo.get_item.return_value = None

    await finder_service._process_job(job)

    mock_job_queue.fail_job.assert_called_once_with(3, "Item MISSING not found", retry=False)
