from typing import Dict

from fastapi import FastAPI

from zotero_cli import __version__


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
    )

    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
