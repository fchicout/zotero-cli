from typing import TYPE_CHECKING, Optional

from zotero_cli.core.config import get_config
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.infra.factory import GatewayFactory

if TYPE_CHECKING:
    from zotero_cli.core.services.job_queue_service import JobQueueService

# Global state for the gateway to persist across requests.
#
# Issue #297: JobQueueService/SnowballGraphService are library-scoped
# (#150/#228), but `serve` is deliberately single-library-per-process -
# these module-level singletons are set once at startup from whichever
# library the process's config resolves to, with no per-request library
# selection anywhere in api/. This is an intentional simplification, not
# a bug: run one `serve` instance per library (on different ports) for
# multi-library HTTP access, the same way the CLI itself is invoked
# per-library via `--config`/`--user`/`system switch`.
_GATEWAY: Optional[ZoteroGateway] = None
_JOB_QUEUE: Optional["JobQueueService"] = None


def get_gateway() -> ZoteroGateway:
    """
    Dependency to retrieve the ZoteroGateway instance.
    Raises RuntimeError if the gateway hasn't been initialized by the startup event.
    """
    if _GATEWAY is None:
        # Fallback for dev/testing: try to load from default config
        try:
            config = get_config()
            return GatewayFactory.get_zotero_gateway(config)
        except Exception:
            raise RuntimeError("ZoteroGateway is not initialized.")
    return _GATEWAY


def set_gateway_instance(gateway: ZoteroGateway) -> None:
    """
    Sets the global gateway instance. Should be called on app startup.
    """
    global _GATEWAY
    _GATEWAY = gateway


def get_job_queue_service() -> "JobQueueService":
    """
    Dependency to retrieve the JobQueueService instance (Issue #150: lets a
    consumer like corbenic-slr poll job status through the API layer instead
    of reading zotero-cli's jobs.sqlite directly).
    Raises RuntimeError if it hasn't been initialized by the startup event.
    """
    if _JOB_QUEUE is None:
        try:
            config = get_config()
            return GatewayFactory.get_job_queue_service(config)
        except Exception:
            raise RuntimeError("JobQueueService is not initialized.")
    return _JOB_QUEUE


def set_job_queue_service_instance(job_queue: "JobQueueService") -> None:
    """
    Sets the global JobQueueService instance. Should be called on app startup.
    """
    global _JOB_QUEUE
    _JOB_QUEUE = job_queue
