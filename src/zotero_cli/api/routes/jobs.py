from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from zotero_cli.api.dependencies import get_job_queue_service
from zotero_cli.core.models import Job
from zotero_cli.core.services.job_queue_service import JobQueueService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _serialize_job(job: Job) -> Dict[str, Any]:
    return {
        "id": job.id,
        "item_key": job.item_key,
        "task_type": job.task_type,
        "status": job.status,
        "attempts": job.attempts,
        "next_retry_at": job.next_retry_at,
        "last_error": job.last_error,
    }


@router.get("", response_model=List[dict])
async def list_jobs(
    job_queue: Annotated[JobQueueService, Depends(get_job_queue_service)],
    task_type: Annotated[Optional[str], Query(description="Filter by task type")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> List[Dict[str, Any]]:
    jobs = job_queue.list_jobs(task_type=task_type, limit=limit)
    return [_serialize_job(j) for j in jobs]


@router.get("/{job_id}", response_model=dict, responses={404: {"description": "Job not found"}})
async def get_job(
    job_id: int,
    job_queue: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Dict[str, Any]:
    job = job_queue.repo.get_job(job_id)
    # A job tagged with a different (non-None) library_id belongs to another
    # project's queue - treat it as not found rather than leaking status
    # across libraries sharing one jobs.sqlite (Issue #150).
    if not job or (
        job.library_id is not None
        and job_queue.library_id is not None
        and job.library_id != job_queue.library_id
    ):
        raise HTTPException(status_code=404, detail="Job not found")

    return _serialize_job(job)
