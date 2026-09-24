import hmac
import ipaddress
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable, Dict, Optional, Sequence

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from zotero_cli import __version__
from zotero_cli.api.dependencies import set_gateway_instance, set_job_queue_service_instance
from zotero_cli.api.routes import collections, items, jobs
from zotero_cli.core.config import get_config
from zotero_cli.infra.factory import GatewayFactory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: Load Config and Init Gateway
    print("Initializing Zotero Gateway...")
    config = get_config()
    gateway = GatewayFactory.get_zotero_gateway(config)
    set_gateway_instance(gateway)
    set_job_queue_service_instance(GatewayFactory.get_job_queue_service(config))
    yield
    # Shutdown: (Optional cleanup)


LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

# `serve` passes its settings through the environment because uvicorn builds
# the app itself (factory=True), in a child process when --reload is on.
ENV_ALLOWED_HOSTS = "ZOTERO_CLI_SERVE_ALLOWED_HOSTS"
ENV_TOKEN = "ZOTERO_CLI_SERVE_TOKEN"  # nosec B105 - an env var name, not a secret


def is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _host_without_port(host_header: str) -> str:
    host = host_header.strip().lower()
    if host.startswith("["):  # [::1]:1969
        return host[1 : host.find("]")] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def create_app(
    allowed_hosts: Optional[Sequence[str]] = None, token: Optional[str] = None
) -> FastAPI:
    """
    Factory function to create the FastAPI application.

    Every request must carry a Host header from `allowed_hosts` (default:
    loopback names only). Without that check, a web page could reach the
    API through DNS rebinding: its own hostname re-pointed at 127.0.0.1,
    making it same-origin with the server. When `token` is set (remote
    mode), every request must also send `Authorization: Bearer <token>`.
    """
    if allowed_hosts is None:
        env_hosts = os.environ.get(ENV_ALLOWED_HOSTS)
        allowed_hosts = env_hosts.split(",") if env_hosts else LOOPBACK_HOSTS
    if token is None:
        token = os.environ.get(ENV_TOKEN) or None
    allowed = {h.strip().lower().strip("[]") for h in allowed_hosts if h.strip()}
    expected_auth = f"Bearer {token}" if token else None

    app = FastAPI(
        title="Zotero CLI API",
        description="Headless API for Zotero CLI",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def guard_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = _host_without_port(request.headers.get("host", ""))
        if "*" not in allowed and host not in allowed:
            return JSONResponse(status_code=400, content={"detail": "Invalid host header"})
        if expected_auth is not None and not hmac.compare_digest(
            request.headers.get("authorization", "").encode(), expected_auth.encode()
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)

    app.include_router(items.router)
    app.include_router(collections.router)
    app.include_router(jobs.router)

    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
