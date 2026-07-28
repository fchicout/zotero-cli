from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import JobRepository
from zotero_cli.core.models import Job


class JobQueueService:
    """
    Service for managing background jobs and retries.

    Scoped to a single library via `library_id` (typically the config's
    `library_id`/`user_id`, resolved once by the factory that constructs this
    service): every job enqueued through this instance is tagged with it, and
    every read is filtered to it, so concurrent SLR projects sharing a jobs
    queue don't silently see each other's jobs. `library_id=None` (the
    default) disables scoping entirely - every job is visible, matching the
    single-user/single-queue behavior this service always had before scoping
    was added.
    """

    def __init__(self, repo: JobRepository, max_attempts: int = 5, library_id: Optional[str] = None):
        self.repo = repo
        self.max_attempts = max_attempts
        self.library_id = library_id

    def enqueue(self, item_key: str, task_type: str, payload: Dict[str, Any]) -> int:
        job = Job(item_key=item_key, task_type=task_type, payload=payload, library_id=self.library_id)
        return self.repo.enqueue(job)

    def pop_next_job(self, task_type: str) -> Optional[Job]:
        return self.repo.get_next_pending(task_type, library_id=self.library_id)

    def list_jobs(self, task_type: Optional[str] = None, limit: int = 100) -> List[Job]:
        return self.repo.list_jobs(task_type=task_type, library_id=self.library_id, limit=limit)

    def complete_job(self, job_id: int, result: Optional[Dict[str, Any]] = None) -> None:
        job = self.repo.get_job(job_id)
        if not job:
            return

        job.status = "COMPLETED"
        if result:
            job.payload["result"] = result
        self.repo.update_job(job)

    def fail_job(self, job_id: int, error: str, retry: bool = True) -> None:
        job = self.repo.get_job(job_id)
        if not job:
            return

        job.attempts += 1
        job.last_error = error

        if retry and job.attempts < self.max_attempts:
            job.status = "RETRY"
            # Exponential backoff: 2^attempts * 60 seconds
            wait_seconds = (2**job.attempts) * 60
            next_retry = datetime.now() + timedelta(seconds=wait_seconds)
            job.next_retry_at = next_retry.strftime("%Y-%m-%d %H:%M:%S")
        else:
            job.status = "FAILED"

        self.repo.update_job(job)
