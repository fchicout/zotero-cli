import os
import tempfile

import pytest

from zotero_cli.core.services.job_queue_service import JobQueueService
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
def job_service(job_repo):
    return JobQueueService(job_repo)


def test_enqueue_and_pop(job_service):
    payload = {"foo": "bar"}
    job_id = job_service.enqueue("ABC123", "fetch_pdf", payload)
    assert job_id is not None

    job = job_service.pop_next_job("fetch_pdf")
    assert job is not None
    assert job.id == job_id
    assert job.item_key == "ABC123"
    assert job.payload == payload
    assert job.status == "PROCESSING"


def test_pop_empty(job_service):
    job = job_service.pop_next_job("fetch_pdf")
    assert job is None


def test_complete_job(job_service, job_repo):
    job_id = job_service.enqueue("ABC123", "fetch_pdf", {"foo": "bar"})
    job_service.pop_next_job("fetch_pdf")

    job_service.complete_job(job_id, {"url": "http://example.com"})

    job = job_repo.get_job(job_id)
    assert job.status == "COMPLETED"
    assert job.payload["result"] == {"url": "http://example.com"}


def test_fail_job_retry(job_service, job_repo):
    job_id = job_service.enqueue("ABC123", "fetch_pdf", {"foo": "bar"})
    job_service.pop_next_job("fetch_pdf")

    job_service.fail_job(job_id, "Network error", retry=True)

    job = job_repo.get_job(job_id)
    assert job.status == "RETRY"
    assert job.attempts == 1
    assert job.last_error == "Network error"
    assert job.next_retry_at is not None


def test_fail_job_no_retry(job_service, job_repo):
    job_id = job_service.enqueue("ABC123", "fetch_pdf", {"foo": "bar"})
    job_service.pop_next_job("fetch_pdf")

    job_service.fail_job(job_id, "Fatal error", retry=False)

    job = job_repo.get_job(job_id)
    assert job.status == "FAILED"
    assert job.attempts == 1


def test_max_attempts_reached(job_service, job_repo):
    job_service.max_attempts = 1
    job_id = job_service.enqueue("ABC123", "fetch_pdf", {"foo": "bar"})
    job_service.pop_next_job("fetch_pdf")

    job_service.fail_job(job_id, "Error 1", retry=True)

    job = job_repo.get_job(job_id)
    assert job.status == "FAILED"
    assert job.attempts == 1
