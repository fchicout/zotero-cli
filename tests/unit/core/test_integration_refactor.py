import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.services.pdf_finder_service import PDFFinderService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.sqlite_repo import SqliteJobRepository


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def job_repo(temp_db):
    return SqliteJobRepository(temp_db)


@pytest.fixture
def item_repo():
    repo = MagicMock()
    return repo


@pytest.fixture
def attachment_repo():
    return MagicMock()


@pytest.fixture
def col_repo():
    repo = MagicMock()
    return repo


@pytest.fixture
def pdf_finder(job_repo, item_repo, attachment_repo):
    from zotero_cli.core.services.job_queue_service import JobQueueService

    jq = JobQueueService(job_repo)
    return PDFFinderService(jq, item_repo, attachment_repo, [])


def test_attachment_service_enqueues_jobs(pdf_finder, col_repo, job_repo):
    # Setup
    item1 = ZoteroItem(key="ITEM1", version=1, item_type="journalArticle")
    item2 = ZoteroItem(key="ITEM2", version=1, item_type="journalArticle")

    col_repo.get_collection_id_by_name.return_value = "COL1"
    col_repo.get_items_in_collection.return_value = [item1, item2]

    service = AttachmentService(
        item_repo=MagicMock(),
        collection_repo=col_repo,
        attachment_repo=MagicMock(),
        note_repo=MagicMock(),
        metadata_aggregator=MagicMock(),
        pdf_finder=pdf_finder,
    )

    # Execute
    with patch.object(service, "_has_pdf_attachment", return_value=False):
        job_ids = service.attach_pdfs_to_collection("My Collection")

    # Verify
    assert len(job_ids) == 2

    jobs = job_repo.list_jobs()
    assert len(jobs) == 2
    assert jobs[0].item_key in ["ITEM1", "ITEM2"]
    assert jobs[1].item_key in ["ITEM1", "ITEM2"]
