import asyncio
import logging
from typing import Optional
from urllib.parse import quote

from zotero_cli.core.models import Job
from zotero_cli.core.services.job_queue_service import JobQueueService
from zotero_cli.core.services.network_gateway import NetworkGateway
from zotero_cli.core.services.snowball_graph import SnowballGraphService
from zotero_cli.core.utils.normalization import is_valid_doi

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

    async def process_jobs(self, count: Optional[int] = None) -> None:
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

    async def _process_job(self, job: Job) -> None:
        job_id = job.id
        # internal invariant, not user input
        assert job_id is not None  # nosec B101

        doi = job.item_key  # We use item_key to store the DOI for these tasks
        task_type = job.task_type
        generation = job.payload.get("generation", 1)

        logger.info(f"Worker: Processing {task_type} for DOI: {doi} (Job {job_id})")

        # Issue #242: doi seeding a backward/forward job can originate
        # from a prior CrossRef/Semantic Scholar API response
        # (ref.get("DOI")/cite_doi) - untrusted third-party metadata fed
        # back into subsequent URL construction. Reject anything that
        # isn't at least DOI-shaped before it reaches _discover_backward/
        # _discover_forward's URL construction, rather than sending
        # garbage to the external API.
        if not is_valid_doi(doi):
            logger.warning(f"Worker: Skipping job {job_id} - not a valid DOI: {doi!r}")
            self.job_queue.fail_job(job_id, f"Invalid DOI: {doi!r}", retry=False)
            return

        try:
            if task_type == self.TASK_BACKWARD:
                await self._discover_backward(doi, generation)
            elif task_type == self.TASK_FORWARD:
                await self._discover_forward(doi, generation)

            self.job_queue.complete_job(job_id)
            self.graph_service.save_graph()
        except Exception as e:
            logger.exception(f"Worker: Task {task_type} failed for {doi}")
            # RetryableError check (NetworkGateway raises this for 429/503)
            from zotero_cli.core.exceptions import RetryableError

            retry = isinstance(e, RetryableError)
            self.job_queue.fail_job(job_id, str(e), retry=retry)

    async def _discover_backward(self, doi: str, generation: int) -> None:
        """
        Fetch references via CrossRef.
        """
        # quote() as defense-in-depth (Issue #242): a DOI-shaped value can
        # still legally contain characters like "?"/"#" that would
        # otherwise inject into the URL path/query.
        url = f"https://api.crossref.org/works/{quote(doi, safe='')}"

        # Polite, proactive pacing (Issue #268, mirroring #223's fix for
        # _discover_forward below): the reactive 429 backoff in
        # NetworkGateway only kicks in *after* a request is already
        # rate-limited - it does nothing to stop a burst of backward-
        # discovery jobs from hammering CrossRef's shared pool in the
        # first place. This gap was simply never backfilled from
        # _discover_forward to this sibling method.
        await asyncio.sleep(1.1)

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

            # CrossRef's per-reference metadata is sparse compared to the
            # full "message.author" array available for the work being
            # fetched itself: a reference entry, when it has author info
            # at all, exposes only a single "author" string (typically
            # just the first author's family name), not a full array
            # (Issue #318). One author name is still strictly better than
            # none for an author-overlap signal, so pass it through rather
            # than discarding it as before.
            ref_author = ref.get("author")
            authors = [ref_author] if ref_author else []

            # Map to metadata stub
            paper_metadata = {
                "doi": ref_doi,
                "title": ref.get("article-title")
                or ref.get("unstructured")
                or f"Reference from {doi}",
                "authors": authors,
            }

            self.graph_service.add_candidate(
                paper_metadata, parent_doi=doi, direction="backward", generation=generation
            )
            count += 1

        logger.info(f"CrossRef: Added {count} backward candidates for {doi}")

    async def _discover_forward(self, doi: str, generation: int) -> None:
        """
        Fetch citations via Semantic Scholar.
        """
        # S2 expects DOI: prefix or just DOI depending on endpoint. quote()
        # as defense-in-depth (Issue #242) - see _discover_backward.
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}/citations"
        params = {"fields": "externalIds,title,authors,year,abstract,isInfluential"}

        # Polite, proactive pacing (Issue #223): the reactive 429 backoff in
        # NetworkGateway/JobQueueService only kicks in *after* a request is
        # already rate-limited - it does nothing to stop a burst of forward-
        # discovery jobs from hammering Semantic Scholar's low, globally-
        # shared unauthenticated pool in the first place. Matches the 1
        # req/sec self-throttle infra/semantic_scholar_api.py already
        # applies to its own (synchronous) requests.
        await asyncio.sleep(1.1)

        headers = {}
        if self.s2_api_key:
            headers["x-api-key"] = self.s2_api_key

        logger.info(f"SemanticScholar: Fetching citations for {doi}")
        try:
            response = await self.gateway.get(url, params=params, headers=headers)
        except ValueError:
            if not self.s2_api_key:
                raise
            # NetworkGateway raises ValueError (not a generic
            # HTTPStatusError) specifically when a 403 survives identity
            # rotation with an auth header present - confirmed live
            # (Issue #223) that a rejected semantic_scholar_api_key gets
            # 403 while the identical unauthenticated request succeeds.
            # Fall back rather than failing the whole job outright.
            logger.warning(
                f"SemanticScholar: configured API key was rejected for {doi} "
                "- retrying unauthenticated."
            )
            await asyncio.sleep(1.1)
            response = await self.gateway.get(url, params=params, headers={})

        data = response.json()

        citations = data.get("data", [])

        count = 0
        for cite in citations:
            citing_paper = cite.get("citingPaper", {})
            cite_doi = citing_paper.get("externalIds", {}).get("DOI")

            if not cite_doi:
                continue

            # Semantic Scholar's "authors" field is a list of
            # {"authorId": ..., "name": ...} objects (Issue #318) - the
            # request already asks for it (`params` above), it was just
            # being discarded here before add_candidate ever saw it.
            authors = [
                a.get("name", "") for a in citing_paper.get("authors", []) if a.get("name")
            ]

            paper_metadata = {
                "doi": cite_doi,
                "title": citing_paper.get("title", ""),
                "abstract": citing_paper.get("abstract", ""),
                "is_influential": cite.get("isInfluential", False),
                "authors": authors,
            }

            self.graph_service.add_candidate(
                paper_metadata, parent_doi=doi, direction="forward", generation=generation
            )
            count += 1

        logger.info(f"SemanticScholar: Added {count} forward candidates for {doi}")
