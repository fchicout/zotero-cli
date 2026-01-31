from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from zotero_cli.core.interfaces import JobRepository
from zotero_cli.core.models import Job


class JobQueueService:
    """
    Service for managing background jobs and retries.
    """

    def __init__(self, repo: JobRepository, max_attempts: int = 5):
        self.repo = repo
        self.max_attempts = max_attempts

    def enqueue(self, item_key: str, task_type: str, payload: Dict[str, Any]) -> int:
        job = Job(item_key=item_key, task_type=task_type, payload=payload)
        return self.repo.enqueue(job)

    def pop_next_job(self, task_type: str) -> Optional[Job]:
        return self.repo.get_next_pending(task_type)

    def complete_job(self, job_id: int, result: Optional[Dict[str, Any]] = None):
        job = self.repo.get_job(job_id)
        if not job:
            return

        job.status = "COMPLETED"
        if result:
            job.payload["result"] = result
        self.repo.update_job(job)

    def fail_job(self, job_id: int, error: str, retry: bool = True):
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
