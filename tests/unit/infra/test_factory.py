from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.infra.factory import GatewayFactory


@pytest.fixture
def mock_config():
    return ZoteroConfig(
        api_key="test_key",
        library_id="123",
        library_type="user",
        database_path="test.sqlite",
    )


def test_get_zotero_gateway_online(mock_config):
    with patch("zotero_cli.infra.factory.ZoteroAPIClient") as mock_client:
        gateway = GatewayFactory.get_zotero_gateway(mock_config, offline=False)
        assert gateway == mock_client.return_value


def test_get_zotero_gateway_offline(mock_config, tmp_path):
    db_file = tmp_path / "zotero.sqlite"
    db_file.write_text("dummy")
    mock_config = ZoteroConfig(
        api_key="test_key",
        library_id="123",
        library_type="user",
        database_path=str(db_file),
    )

    gateway = GatewayFactory.get_zotero_gateway(mock_config, offline=True)
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    assert isinstance(gateway, SqliteZoteroGateway)


def test_get_zotero_gateway_offline_no_path(mock_config):
    mock_config = ZoteroConfig(
        api_key="test_key",
        library_id="123",
        library_type="user",
        database_path=None,
    )
    with patch("sys.stderr", new_callable=MagicMock):
        with pytest.raises(SystemExit):
            GatewayFactory.get_zotero_gateway(mock_config, offline=True)


def test_get_job_queue_service(mock_config):
    service = GatewayFactory.get_job_queue_service(mock_config)
    from zotero_cli.core.services.job_queue_service import JobQueueService

    assert isinstance(service, JobQueueService)


def test_get_pdf_finder_service(mock_config):
    service = GatewayFactory.get_pdf_finder_service(mock_config)
    from zotero_cli.core.services.pdf_finder_service import PDFFinderService

    assert isinstance(service, PDFFinderService)


def test_get_rag_service(mock_config):
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_vector_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_embedding_provider"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_attachment_service"),
    ):
        service = GatewayFactory.get_rag_service(mock_config)
        from zotero_cli.core.services.rag_service import RAGServiceBase

        assert isinstance(service, RAGServiceBase)


def test_get_embedding_provider_gemini(mock_config):
    mock_config = ZoteroConfig(
        api_key="key",
        library_id="123",
        library_type="user",
        gemini_api_key="gemini_key",
    )
    provider = GatewayFactory.get_embedding_provider(mock_config)
    from zotero_cli.core.services.embedding_provider import GeminiEmbeddingProvider

    assert isinstance(provider, GeminiEmbeddingProvider)


def test_get_embedding_provider_openai(mock_config):
    mock_config = ZoteroConfig(
        api_key="key",
        library_id="123",
        library_type="user",
        openai_api_key="openai_key",
    )
    provider = GatewayFactory.get_embedding_provider(mock_config)
    from zotero_cli.core.services.embedding_provider import OpenAIEmbeddingProvider

    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_get_item_repository(mock_config):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"):
        repo = GatewayFactory.get_item_repository(mock_config)
        from zotero_cli.infra.repositories import ZoteroItemRepository

        assert isinstance(repo, ZoteroItemRepository)


def test_get_collection_repository(mock_config):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"):
        repo = GatewayFactory.get_collection_repository(mock_config)
        from zotero_cli.infra.repositories import ZoteroCollectionRepository

        assert isinstance(repo, ZoteroCollectionRepository)


def test_get_attachment_repository(mock_config):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"):
        repo = GatewayFactory.get_attachment_repository(mock_config)
        from zotero_cli.infra.repositories import ZoteroAttachmentRepository

        assert isinstance(repo, ZoteroAttachmentRepository)


def test_get_note_repository(mock_config):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"):
        repo = GatewayFactory.get_note_repository(mock_config)
        from zotero_cli.infra.repositories import ZoteroNoteRepository

        assert isinstance(repo, ZoteroNoteRepository)


def test_get_tag_repository(mock_config):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"):
        repo = GatewayFactory.get_tag_repository(mock_config)
        from zotero_cli.infra.repositories import ZoteroTagRepository

        assert isinstance(repo, ZoteroTagRepository)


def test_get_collection_service(mock_config):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"):
        service = GatewayFactory.get_collection_service(mock_config)
        from zotero_cli.core.services.collection_service import CollectionService

        assert isinstance(service, CollectionService)


def test_get_import_service(mock_config):
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_item_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_repository"),
    ):
        service = GatewayFactory.get_import_service(mock_config)
        from zotero_cli.core.services.import_service import ImportService

        assert isinstance(service, ImportService)


def test_get_enrichment_service(mock_config):
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_item_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_attachment_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_note_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_metadata_aggregator"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_purge_service"),
    ):
        service = GatewayFactory.get_enrichment_service(mock_config)
        from zotero_cli.core.services.enrichment_service import EnrichmentService

        assert isinstance(service, EnrichmentService)


def test_get_screening_service(mock_config):
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_item_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_note_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_tag_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service"),
    ):
        service = GatewayFactory.get_screening_service(mock_config)
        from zotero_cli.core.services.screening_service import ScreeningService

        assert isinstance(service, ScreeningService)


def test_get_snowball_worker(mock_config):
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_network_gateway"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_snowball_graph_service"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service"),
    ):
        service = GatewayFactory.get_snowball_worker(mock_config)
        from zotero_cli.core.services.snowball_worker import SnowballDiscoveryWorker

        assert isinstance(service, SnowballDiscoveryWorker)


def test_get_metadata_aggregator(mock_config):
    service = GatewayFactory.get_metadata_aggregator(mock_config)
    from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService

    assert isinstance(service, MetadataAggregatorService)


def test_get_config_not_provided():
    with patch("zotero_cli.core.config.get_config") as mock_get:
        GatewayFactory.get_zotero_gateway()
        mock_get.assert_called_once()


def test_get_arxiv_gateway():
    from zotero_cli.infra.arxiv_lib import ArxivLibGateway

    assert isinstance(GatewayFactory.get_arxiv_gateway(), ArxivLibGateway)


def test_get_bibtex_gateway():
    from zotero_cli.infra.bibtex_lib import BibtexLibGateway

    assert isinstance(GatewayFactory.get_bibtex_gateway(), BibtexLibGateway)


def test_get_ris_gateway():
    from zotero_cli.infra.ris_lib import RisLibGateway

    assert isinstance(GatewayFactory.get_ris_gateway(), RisLibGateway)


def test_get_springer_csv_gateway():
    from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway

    assert isinstance(GatewayFactory.get_springer_csv_gateway(), SpringerCsvLibGateway)


def test_get_ieee_csv_gateway():
    from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway

    assert isinstance(GatewayFactory.get_ieee_csv_gateway(), IeeeCsvLibGateway)


def test_get_canonical_csv_gateway():
    from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway

    assert isinstance(GatewayFactory.get_canonical_csv_gateway(), CanonicalCsvLibGateway)


def test_get_network_gateway():
    from zotero_cli.core.services.network_gateway import NetworkGateway

    assert isinstance(GatewayFactory.get_network_gateway(), NetworkGateway)


def test_get_unpaywall_resolver(mock_config):
    from zotero_cli.core.services.resolvers.unpaywall import UnpaywallResolver

    assert isinstance(GatewayFactory.get_unpaywall_resolver(mock_config), UnpaywallResolver)


def test_get_generic_resolvers():
    with patch("zotero_cli.core.config.get_config_path") as mock_path:
        mock_path.return_value = None
        resolvers = GatewayFactory.get_generic_resolvers()
        assert isinstance(resolvers, list)


def test_get_generic_resolvers_with_file(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yaml_file = config_dir / "resolvers.yaml"
    yaml_file.write_text("resolvers: []")

    with patch("zotero_cli.core.config.get_config_path") as mock_path:
        mock_path.return_value = config_dir / "config.toml"
        resolvers = GatewayFactory.get_generic_resolvers()
        assert isinstance(resolvers, list)


def test_get_snowball_graph_service():
    from zotero_cli.core.services.snowball_graph import SnowballGraphService

    assert isinstance(GatewayFactory.get_snowball_graph_service(), SnowballGraphService)


def test_get_snowball_ingestion_service(mock_config):
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_snowball_graph_service"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_metadata_aggregator"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_item_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_repository"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
    ):
        from zotero_cli.core.services.snowball_ingestion import SnowballIngestionService

        assert isinstance(
            GatewayFactory.get_snowball_ingestion_service(mock_config), SnowballIngestionService
        )


def test_get_vector_repository(mock_config):
    from zotero_cli.infra.sqlite_vector_repo import SQLiteVectorRepository

    assert isinstance(GatewayFactory.get_vector_repository(mock_config), SQLiteVectorRepository)


def test_get_purge_service(mock_config):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"):
        from zotero_cli.core.services.purge_service import PurgeService

        assert isinstance(GatewayFactory.get_purge_service(mock_config), PurgeService)


def test_get_arxiv_resolver():
    from zotero_cli.core.services.resolvers.arxiv import ArXivResolver

    assert isinstance(GatewayFactory.get_arxiv_resolver(), ArXivResolver)


def test_get_openalex_resolver():
    from zotero_cli.core.services.resolvers.openalex import OpenAlexResolver

    assert isinstance(GatewayFactory.get_openalex_resolver(), OpenAlexResolver)


def test_get_zotero_gateway_group_parsing():
    mock_config = ZoteroConfig(
        api_key="key",
        library_id=None,
        library_type=None,
        user_id="123",
        target_group_url="https://www.zotero.org/groups/456/items",
    )
    with patch("zotero_cli.infra.factory.ZoteroAPIClient") as mock_client:
        GatewayFactory.get_zotero_gateway(mock_config)
        # Check that library_id was parsed from URL
        args, _ = mock_client.call_args
        assert args[1] == "456"
        assert args[2] == "group"


def test_get_zotero_gateway_user_id_fallback():
    mock_config = ZoteroConfig(
        api_key="key",
        library_id=None,
        library_type=None,
        user_id="123",
        target_group_url=None,
    )
    with patch("zotero_cli.infra.factory.ZoteroAPIClient") as mock_client:
        GatewayFactory.get_zotero_gateway(mock_config)
        args, _ = mock_client.call_args
        assert args[1] == "123"
        assert args[2] == "user"
