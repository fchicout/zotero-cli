"""ServiceFactory builds each service from the repositories it needs."""

from unittest.mock import create_autospec

import pytest

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.interfaces import (
    CollectionRepository,
    ItemRepository,
    MetadataProvider,
    ZoteroGateway,
)
from zotero_cli.core.services.diagnostics_service import DiagnosticsService
from zotero_cli.core.services.export_service import ExportService
from zotero_cli.core.services.integrity_service import IntegrityService
from zotero_cli.core.services.restore_service import RestoreService
from zotero_cli.core.services.sandbox_service import SandboxService
from zotero_cli.infra.metadata_client_factory import MetadataClientFactory
from zotero_cli.infra.repository_factory import RepositoryFactory
from zotero_cli.infra.service_factory import ServiceFactory

CONFIG = ZoteroConfig(api_key="k", library_id="1", library_type="user")


@pytest.fixture(autouse=True)
def repositories(monkeypatch):
    gateway = create_autospec(ZoteroGateway, instance=True)
    collections = create_autospec(CollectionRepository, instance=True)
    items = create_autospec(ItemRepository, instance=True)
    monkeypatch.setattr(RepositoryFactory, "get_zotero_gateway", lambda *a, **k: gateway)
    monkeypatch.setattr(RepositoryFactory, "get_collection_repository", lambda *a, **k: collections)
    monkeypatch.setattr(RepositoryFactory, "get_item_repository", lambda *a, **k: items)
    monkeypatch.setattr(
        MetadataClientFactory,
        "get_metadata_aggregator",
        lambda *a, **k: create_autospec(MetadataProvider, instance=True),
    )
    return {"gateway": gateway, "collections": collections, "items": items}


def test_export_service_takes_the_collection_repository(repositories):
    service = ServiceFactory.get_export_service(CONFIG, offline=True)

    assert isinstance(service, ExportService)
    assert service.collection_repo is repositories["collections"]
    assert service.bibliography_formatter is not None


def test_restore_service_takes_the_gateway(repositories):
    service = ServiceFactory.get_restore_service(CONFIG)

    assert isinstance(service, RestoreService)
    assert service.gateway is repositories["gateway"]


def test_integrity_service_takes_the_gateway(repositories):
    service = ServiceFactory.get_integrity_service(CONFIG)

    assert isinstance(service, IntegrityService)
    assert service.gateway is repositories["gateway"]


def test_sandbox_service_takes_collections_and_items(repositories):
    service = ServiceFactory.get_sandbox_service(CONFIG)

    assert isinstance(service, SandboxService)
    assert service.collection_repo is repositories["collections"]
    assert service.item_repo is repositories["items"]


def test_diagnostics_service_runs_without_ai_providers(repositories):
    service = ServiceFactory.get_diagnostics_service(CONFIG)

    assert isinstance(service, DiagnosticsService)
    assert service.gateway is repositories["gateway"]
    assert service.gateway_error is None
