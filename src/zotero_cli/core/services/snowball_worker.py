import logging
from typing import Optional

from zotero_cli.core.models import Job
from zotero_cli.core.services.job_queue_service import JobQueueService
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.services.snowball_graph import SnowballGraphService

logger = logging.getLogger(__name__)


class SnowballDiscoveryWorker:
    """
    Background worker for discovering papers via forward and backward snowballing.
    Populates the SnowballGraphService with candidate papers.
    """

    TASK_BACKWARD = "discover_backward"
    TASK_FORWARD = "discover_forward"

    def __init__(
        self,
        gateway: NetworkGateway,
        graph_service: SnowballGraphService,
        job_queue: JobQueueService,
        s2_api_key: Optional[str] = None,
    ):
        self.gateway = gateway
        self.graph_service = graph_service
        self.job_queue = job_queue
        self.s2_api_key = s2_api_key

    async def process_jobs(self, count: Optional[int] = None):
        """
        Pops and processes jobs from the queue.
        """
        processed = 0
        while True:
            if count is not None and processed >= count:
                break

            # Try backward jobs
            job = self.job_queue.pop_next_job(self.TASK_BACKWARD)
            if not job:
                # Try forward jobs
                job = self.job_queue.pop_next_job(self.TASK_FORWARD)

            if not job:
                break

            await self._process_job(job)
            processed += 1

    async def _process_job(self, job: Job):
        job_id = job.id
        assert job_id is not None

        doi = job.item_key  # We use item_key to store the DOI for these tasks
        task_type = job.task_type
        generation = job.payload.get("generation", 1)

        logger.info(f"Worker: Processing {task_type} for DOI: {doi} (Job {job_id})")

        try:
            if task_type == self.TASK_BACKWARD:
                await self._discover_backward(doi, generation)
            elif task_type == self.TASK_FORWARD:
                await self._discover_forward(doi, generation)

            self.job_queue.complete_job(job_id)
            self.graph_service.save_graph()
        except Exception as e:
            logger.error(f"Worker: Task {task_type} failed for {doi}: {e}")
            # RetryableError check (NetworkGateway raises this for 429/503)
            from zotero_cli.core.exceptions import RetryableError

            retry = isinstance(e, RetryableError)
            self.job_queue.fail_job(job_id, str(e), retry=retry)

    async def _discover_backward(self, doi: str, generation: int):
        """
        Fetch references via CrossRef.
        """
        url = f"https://api.crossref.org/works/{doi}"
        logger.info(f"CrossRef: Fetching references for {doi}")

        response = await self.gateway.get(url)
        data = response.json()

        message = data.get("message", {})
        references = message.get("reference", [])

        count = 0
        for ref in references:
            ref_doi = ref.get("DOI")
            if not ref_doi:
                continue

            # Map to metadata stub
            paper_metadata = {
                "doi": ref_doi,
                "title": ref.get("article-title")
                or ref.get("unstructured")
                or f"Reference from {doi}",
            }

            self.graph_service.add_candidate(
                paper_metadata, parent_doi=doi, direction="backward", generation=generation
            )
            count += 1

        logger.info(f"CrossRef: Added {count} backward candidates for {doi}")

    async def _discover_forward(self, doi: str, generation: int):
        """
        Fetch citations via Semantic Scholar.
        """
        # S2 expects DOI: prefix or just DOI depending on endpoint
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}/citations"
        params = {"fields": "title,authors,year,abstract,isInfluential"}

        headers = {}
        if self.s2_api_key:
            headers["x-api-key"] = self.s2_api_key

        logger.info(f"SemanticScholar: Fetching citations for {doi}")
        response = await self.gateway.get(url, params=params, headers=headers)
        data = response.json()

        citations = data.get("data", [])

        count = 0
        for cite in citations:
            citing_paper = cite.get("citingPaper", {})
            cite_doi = citing_paper.get("externalIds", {}).get("DOI")

            if not cite_doi:
                continue

            paper_metadata = {
                "doi": cite_doi,
                "title": citing_paper.get("title", ""),
                "abstract": citing_paper.get("abstract", ""),
                "is_influential": cite.get("isInfluential", False),
            }

            self.graph_service.add_candidate(
                paper_metadata, parent_doi=doi, direction="forward", generation=generation
            )
            count += 1

        logger.info(f"SemanticScholar: Added {count} forward candidates for {doi}")
