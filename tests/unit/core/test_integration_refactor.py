import os
import tempfile
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.pdf_finder_service import PDFFinderService
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
