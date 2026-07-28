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


def test_unscoped_service_ignores_library_id(job_repo):
    """A service with no library_id (the default) is unscoped: it enqueues
    untagged jobs and sees every job, matching pre-#150 behavior."""
    service = JobQueueService(job_repo)
    job_id = service.enqueue("ABC123", "fetch_pdf", {})

    job = job_repo.get_job(job_id)
    assert job.library_id is None
    assert len(service.list_jobs()) == 1


def test_scoped_services_do_not_see_each_others_jobs(job_repo):
    """Issue #150: two concurrent SLR projects sharing one jobs.sqlite must
    not see or pop each other's jobs."""
    project_a = JobQueueService(job_repo, library_id="lib-A")
    project_b = JobQueueService(job_repo, library_id="lib-B")

    id_a = project_a.enqueue("ITEM_A", "fetch_pdf", {})
    id_b = project_b.enqueue("ITEM_B", "fetch_pdf", {})

    jobs_a = project_a.list_jobs()
    jobs_b = project_b.list_jobs()
    assert [j.id for j in jobs_a] == [id_a]
    assert [j.id for j in jobs_b] == [id_b]

    popped = project_a.pop_next_job("fetch_pdf")
    assert popped is not None
    assert popped.id == id_a
    assert project_a.pop_next_job("fetch_pdf") is None  # A's queue is now empty
    popped_b = project_b.pop_next_job("fetch_pdf")
    assert popped_b is not None
    assert popped_b.id == id_b  # B's job untouched


def test_scoped_service_still_sees_legacy_unscoped_jobs(job_repo):
    """A job enqueued before library scoping existed (library_id=NULL) must
    stay visible/poppable rather than becoming silently orphaned."""
    unscoped = JobQueueService(job_repo)
    legacy_id = unscoped.enqueue("LEGACY", "fetch_pdf", {})

    scoped = JobQueueService(job_repo, library_id="lib-A")
    assert legacy_id in [j.id for j in scoped.list_jobs()]
    popped = scoped.pop_next_job("fetch_pdf")
    assert popped is not None
    assert popped.id == legacy_id
