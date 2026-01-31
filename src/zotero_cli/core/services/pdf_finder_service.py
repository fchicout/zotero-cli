import logging
from pathlib import Path
from typing import List, Optional

from zotero_cli.core.interfaces import AttachmentRepository, ItemRepository, PDFResolver
from zotero_cli.core.models import Job
from zotero_cli.core.services.job_queue_service import JobQueueService

logger = logging.getLogger(__name__)


class PDFFinderService:
    """
    Orchestrates the discovery and attachment of PDFs using a chain of resolvers.
    Integrates with JobQueue for persistent, traceable background processing.
    """

    def __init__(
        self,
        job_queue: JobQueueService,
        item_repo: ItemRepository,
        attachment_repo: AttachmentRepository,
        resolvers: List[PDFResolver],
    ):
        self.job_queue = job_queue
        self.item_repo = item_repo
        self.attachment_repo = attachment_repo
        self.resolvers = resolvers

    def enqueue_find_pdf(self, item_key: str) -> int:
        """
        Enqueues a job to find and attach a PDF for the given item.
        """
        return self.job_queue.enqueue(item_key, "fetch_pdf", {})

    async def process_jobs(self, count: Optional[int] = None):
        """
        Processes pending fetch_pdf jobs.
        """
        processed = 0
        while True:
            if count is not None and processed >= count:
                break

            job = self.job_queue.pop_next_job("fetch_pdf")
            if not job:
                break

            await self._process_job(job)
            processed += 1

    async def _process_job(self, job: Job):
        item_key = job.item_key
        job_id = job.id
        assert job_id is not None, "Job ID must not be None for processing"

        logger.info(f"Worker: Processing job {job_id} for item {item_key}")

        item = self.item_repo.get_item(item_key)
        if not item:
            self.job_queue.fail_job(job_id, f"Item {item_key} not found", retry=False)
            return

        # Resolver Chain Execution
        pdf_path: Optional[Path] = None
        method_used: Optional[str] = None

        for resolver in self.resolvers:
            try:
                resolver_name = resolver.__class__.__name__
                logger.debug(f"Trying resolver {resolver_name} for {item_key}")
                pdf_path = await resolver.resolve(item)
                if pdf_path:
                    method_used = resolver_name
                    break
            except Exception as e:
                logger.warning(f"Resolver {resolver.__class__.__name__} failed for {item_key}: {e}")

        if pdf_path:
            try:
                logger.info(f"Success! PDF found via {method_used}. Uploading to Zotero...")
                success = self.attachment_repo.upload_attachment(
                    item_key, str(pdf_path), mime_type="application/pdf"
                )
                if success:
                    self.job_queue.complete_job(job_id, {"method": method_used, "path": str(pdf_path)})
                else:
                    self.job_queue.fail_job(job_id, "Zotero attachment upload failed")
            finally:
                # Cleanup
                if pdf_path.exists():
                    pdf_path.unlink()
        else:
            logger.info(f"Failed: No resolver could find a PDF for {item_key}")
            self.job_queue.fail_job(job_id, "No PDF found by any resolver", retry=True)
