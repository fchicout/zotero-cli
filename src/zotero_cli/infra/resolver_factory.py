import logging
from typing import TYPE_CHECKING, List, Optional

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.utils.notify import notify_or_log
from zotero_cli.infra.config_resolution import resolve_config
from zotero_cli.infra.metadata_client_factory import MetadataClientFactory

if TYPE_CHECKING:
    from zotero_cli.core.interfaces import PDFResolver
    from zotero_cli.core.services.network_gateway import NetworkGateway

logger = logging.getLogger(__name__)


class ResolverFactory:
    """
    Constructs PDF-resolution chains (Unpaywall/OpenAlex/arXiv/Semantic
    Scholar/BDTD/YAML-configured scrapers) and the snowball citation-discovery
    services built on top of the same network gateway.
    """

    @staticmethod
    def get_network_gateway(config: Optional[ZoteroConfig] = None) -> "NetworkGateway":
        from zotero_cli.core.services.network_gateway import NetworkGateway
        from zotero_cli.core.utils.user_agent import user_agent

        config = resolve_config(config)
        # The user's own contact address, for the polite pools (Issue #407).
        return NetworkGateway(user_agent(config.unpaywall_email))

    @staticmethod
    def get_unpaywall_resolver(config: Optional[ZoteroConfig] = None) -> "PDFResolver":
        config = resolve_config(config)

        from zotero_cli.core.services.resolvers.unpaywall import UnpaywallResolver

        gateway = ResolverFactory.get_network_gateway(config)
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
        config = resolve_config(config)

        from zotero_cli.core.services.resolvers.semantic_scholar import SemanticScholarResolver

        gateway = ResolverFactory.get_network_gateway(config)
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
            notify_or_log(
                None,
                logger,
                f"Warning: Failed to load generic resolvers from {yaml_path}: {e}",
                logging.WARNING,
            )
            logger.warning("Failed to load generic resolvers from %s: %s", yaml_path, e)
            return []
