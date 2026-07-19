import sys
from typing import TYPE_CHECKING, List, Optional

from zotero_cli.core.config import ZoteroConfig, get_storage_dir
from zotero_cli.infra.metadata_client_factory import MetadataClientFactory
from zotero_cli.infra.repository_factory import RepositoryFactory

if TYPE_CHECKING:
    from zotero_cli.core.interfaces import PDFResolver
    from zotero_cli.core.services.network_gateway import NetworkGateway
    from zotero_cli.core.services.snowball_graph import SnowballGraphService
    from zotero_cli.core.services.snowball_ingestion import SnowballIngestionService
    from zotero_cli.core.services.snowball_worker import SnowballDiscoveryWorker


class ResolverFactory:
    """
    Constructs PDF-resolution chains (Unpaywall/OpenAlex/arXiv/Semantic
    Scholar/BDTD/YAML-configured scrapers) and the snowball citation-discovery
    services built on top of the same network gateway.
    """

    @staticmethod
    def get_network_gateway() -> "NetworkGateway":
        from zotero_cli.core.services.identity_manager import IdentityManager
        from zotero_cli.core.services.network_gateway import NetworkGateway

        # IdentityManager is lightweight but holds state (index).
        # ideally we singleton it, but for now we create fresh.
        # Future optimization: cache it at class level if needed.
        im = IdentityManager()
        return NetworkGateway(im)

    @staticmethod
    def get_unpaywall_resolver(config: Optional[ZoteroConfig] = None) -> "PDFResolver":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.services.resolvers.unpaywall import UnpaywallResolver

        gateway = ResolverFactory.get_network_gateway()
        return UnpaywallResolver(gateway, email=config.unpaywall_email)

    @staticmethod
    def get_openalex_resolver() -> "PDFResolver":
        from zotero_cli.core.services.resolvers.openalex import OpenAlexResolver

        client = MetadataClientFactory.get_openalex_client()
        return OpenAlexResolver(client)

    @staticmethod
    def get_arxiv_resolver() -> "PDFResolver":
        from zotero_cli.core.services.resolvers.arxiv import ArXivResolver

        gateway = ResolverFactory.get_network_gateway()
        return ArXivResolver(gateway)

    @staticmethod
    def get_semantic_scholar_resolver(config: Optional[ZoteroConfig] = None) -> "PDFResolver":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.services.resolvers.semantic_scholar import SemanticScholarResolver

        gateway = ResolverFactory.get_network_gateway()
        return SemanticScholarResolver(gateway, api_key=config.semantic_scholar_api_key)

    @staticmethod
    def get_bdtd_resolver() -> "PDFResolver":
        from zotero_cli.core.services.resolvers.bdtd import BDTDResolver

        gateway = ResolverFactory.get_network_gateway()
        return BDTDResolver(gateway)

    @staticmethod
    def get_generic_resolvers() -> List["PDFResolver"]:
        from zotero_cli.core.config import get_config_path

        config_path = get_config_path()
        if not config_path:
            return []

        yaml_path = config_path.parent / "resolvers.yaml"
        if not yaml_path.exists():
            return []

        import yaml

        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)

            resolvers_config = data.get("resolvers", [])
            from zotero_cli.core.services.resolvers.generic_scraper import GenericScraperResolver

            gateway = ResolverFactory.get_network_gateway()

            return [GenericScraperResolver(gateway, cfg) for cfg in resolvers_config]
        except Exception as e:
            print(
                f"Warning: Failed to load generic resolvers from {yaml_path}: {e}", file=sys.stderr
            )
            return []

    @staticmethod
    def get_snowball_graph_service() -> "SnowballGraphService":
        db_dir = get_storage_dir()
        db_dir.mkdir(parents=True, exist_ok=True)
        storage_path = db_dir / "discovery_graph.json"

        from zotero_cli.core.services.snowball_graph import SnowballGraphService

        return SnowballGraphService(storage_path)

    @staticmethod
    def get_snowball_worker(config: Optional[ZoteroConfig] = None) -> "SnowballDiscoveryWorker":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        gateway = ResolverFactory.get_network_gateway()
        graph_service = ResolverFactory.get_snowball_graph_service()

        # Lazy import: ServiceFactory imports ResolverFactory (for PDF-finder
        # resolvers), so this back-reference must stay function-local to avoid
        # a circular module import.
        from zotero_cli.infra.service_factory import ServiceFactory

        job_queue = ServiceFactory.get_job_queue_service(config)

        from zotero_cli.core.services.snowball_worker import SnowballDiscoveryWorker

        return SnowballDiscoveryWorker(
            gateway, graph_service, job_queue, s2_api_key=config.semantic_scholar_api_key
        )

    @staticmethod
    def get_snowball_ingestion_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SnowballIngestionService":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        graph_service = ResolverFactory.get_snowball_graph_service()
        metadata_service = MetadataClientFactory.get_metadata_aggregator(config)
        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = RepositoryFactory.get_collection_repository(
            config, force_user, offline=offline
        )

        from zotero_cli.core.services.duplicate_service import DuplicateFinder

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        duplicate_finder = DuplicateFinder(gateway)

        from zotero_cli.core.services.snowball_ingestion import SnowballIngestionService

        return SnowballIngestionService(
            graph_service, metadata_service, item_repo, col_repo, duplicate_finder
        )
