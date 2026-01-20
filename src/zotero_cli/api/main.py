from typing import Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI

from zotero_cli import __version__
from zotero_cli.core.config import get_config
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.api.dependencies import set_gateway_instance
from zotero_cli.api.routes import items


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load Config and Init Gateway
    print("Initializing Zotero Gateway...")
    config = get_config()
    gateway = GatewayFactory.get_zotero_gateway(config)
    set_gateway_instance(gateway)
    yield
    # Shutdown: (Optional cleanup)


def create_app() -> FastAPI:
    """
    Factory function to create the FastAPI application.
    """
    app = FastAPI(
        title="Zotero CLI API",
        description="Headless API for Zotero CLI",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.include_router(items.router)

    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
