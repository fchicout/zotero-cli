from typing import TYPE_CHECKING, List, Optional

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
    TagRepository,
)
from zotero_cli.infra.ai_provider_factory import AIProviderFactory
from zotero_cli.infra.metadata_client_factory import MetadataClientFactory
from zotero_cli.infra.repository_factory import RepositoryFactory
from zotero_cli.infra.resolver_factory import ResolverFactory
from zotero_cli.infra.service_factory import ServiceFactory

if TYPE_CHECKING:
    from zotero_cli.core.interfaces import (
        EmbeddingProvider,
        LLMProvider,
        PDFResolver,
        RAGService,
        VectorRepository,
        ZoteroGateway,
    )
    from zotero_cli.core.services.attachment_service import AttachmentService
    from zotero_cli.core.services.audit_service import AuditService
    from zotero_cli.core.services.collection_service import CollectionService
    from zotero_cli.core.services.enrichment_service import EnrichmentService
    from zotero_cli.core.services.export_service import ExportService
    from zotero_cli.core.services.extraction_service import ExtractionService
    from zotero_cli.core.services.import_service import ImportService
    from zotero_cli.core.services.job_queue_service import JobQueueService
    from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
    from zotero_cli.core.services.network_gateway import NetworkGateway
    from zotero_cli.core.services.pdf_finder_service import PDFFinderService
    from zotero_cli.core.services.purge_service import PurgeService
    from zotero_cli.core.services.restore_service import RestoreService
    from zotero_cli.core.services.screening_service import ScreeningService
    from zotero_cli.core.services.sdb.sdb_service import SDBService
    from zotero_cli.core.services.slr.citation_service import CitationService
    from zotero_cli.core.services.slr.csv_inbound import CSVInboundService
    from zotero_cli.core.services.slr.integrity import IntegrityService
    from zotero_cli.core.services.slr.orchestrator import SLROrchestrator
    from zotero_cli.core.services.slr.snapshot import SnapshotService
    from zotero_cli.core.services.slr.status_service import SLRStatusService
    from zotero_cli.core.services.snowball_graph import SnowballGraphService
    from zotero_cli.core.services.snowball_ingestion import SnowballIngestionService
    from zotero_cli.core.services.snowball_worker import SnowballDiscoveryWorker
    from zotero_cli.core.services.speech_service import SpeechService
    from zotero_cli.core.services.tag_service import TagService
    from zotero_cli.core.services.transfer_service import TransferService
    from zotero_cli.core.services.verify_service import VerifyService
    from zotero_cli.infra.arxiv_lib import ArxivLibGateway
    from zotero_cli.infra.bdtd_api import BDTDAPIClient
    from zotero_cli.infra.bibtex_lib import BibtexLibGateway
    from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway
    from zotero_cli.infra.dblp_api import DBLPAPIClient
    from zotero_cli.infra.eric_api import ERICAPIClient
    from zotero_cli.infra.hal_api import HALAPIClient
    from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
    from zotero_cli.infra.inspire_hep_api import InspireHEPAPIClient
    from zotero_cli.infra.openalex_api import OpenAlexAPIClient
    from zotero_cli.infra.pubmed_api import PubMedAPIClient
    from zotero_cli.infra.ris_lib import RisLibGateway
    from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway
    from zotero_cli.infra.zbmath_api import ZBMathAPIClient


class GatewayFactory:
    """
    Central facade for constructing Zotero gateways, repositories, external
    metadata clients, PDF resolvers, AI/RAG providers, and domain services.

    Internally delegates to 5 focused factories (see repository_factory.py,
    metadata_client_factory.py, resolver_factory.py, ai_provider_factory.py,
    service_factory.py, all in this package); this class exists purely so
    existing call sites (CLI commands) keep a single, stable entry point.
    """

    @staticmethod
    def get_zotero_gateway(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        require_group: bool = True,
        offline: Optional[bool] = None,
    ) -> "ZoteroGateway":
        return RepositoryFactory.get_zotero_gateway(config, force_user, require_group, offline)

    @staticmethod
    def get_item_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> ItemRepository:
        return RepositoryFactory.get_item_repository(config, force_user, offline)

    @staticmethod
    def get_collection_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> CollectionRepository:
        return RepositoryFactory.get_collection_repository(config, force_user, offline)

    @staticmethod
    def get_tag_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> TagRepository:
        return RepositoryFactory.get_tag_repository(config, force_user, offline)

    @staticmethod
    def get_note_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> NoteRepository:
        return RepositoryFactory.get_note_repository(config, force_user, offline)

    @staticmethod
    def get_attachment_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> AttachmentRepository:
        return RepositoryFactory.get_attachment_repository(config, force_user, offline)

    @staticmethod
    def get_openalex_client(config: Optional[ZoteroConfig] = None) -> "OpenAlexAPIClient":
        return MetadataClientFactory.get_openalex_client(config)

    @staticmethod
    def get_pubmed_client(config: Optional[ZoteroConfig] = None) -> "PubMedAPIClient":
        return MetadataClientFactory.get_pubmed_client(config)

    @staticmethod
    def get_zbmath_client() -> "ZBMathAPIClient":
        return MetadataClientFactory.get_zbmath_client()

    @staticmethod
    def get_eric_client() -> "ERICAPIClient":
        return MetadataClientFactory.get_eric_client()

    @staticmethod
    def get_dblp_client() -> "DBLPAPIClient":
        return MetadataClientFactory.get_dblp_client()

    @staticmethod
    def get_hal_client() -> "HALAPIClient":
        return MetadataClientFactory.get_hal_client()

    @staticmethod
    def get_bdtd_client() -> "BDTDAPIClient":
        return MetadataClientFactory.get_bdtd_client()

    @staticmethod
    def get_inspire_hep_client() -> "InspireHEPAPIClient":
        return MetadataClientFactory.get_inspire_hep_client()

    @staticmethod
    def get_metadata_aggregator(
        config: Optional[ZoteroConfig] = None,
    ) -> "MetadataAggregatorService":
        return MetadataClientFactory.get_metadata_aggregator(config)

    @staticmethod
    def get_attachment_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "AttachmentService":
        return ServiceFactory.get_attachment_service(config, force_user, offline)

    @staticmethod
    def get_collection_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "CollectionService":
        return ServiceFactory.get_collection_service(config, force_user, offline)

    @staticmethod
    def get_export_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ExportService":
        return ServiceFactory.get_export_service(config, force_user, offline)

    @staticmethod
    def get_transfer_service() -> "TransferService":
        return ServiceFactory.get_transfer_service()

    @staticmethod
    def get_enrichment_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "EnrichmentService":
        return ServiceFactory.get_enrichment_service(config, force_user, offline)

    @staticmethod
    def get_sdb_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SDBService":
        return ServiceFactory.get_sdb_service(config, force_user, offline)

    @staticmethod
    def get_audit_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "AuditService":
        return ServiceFactory.get_audit_service(config, force_user, offline)

    @staticmethod
    def get_restore_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "RestoreService":
        return ServiceFactory.get_restore_service(config, force_user, offline)

    @staticmethod
    def get_integrity_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "IntegrityService":
        return ServiceFactory.get_integrity_service(config, force_user, offline)

    @staticmethod
    def get_snapshot_service() -> "SnapshotService":
        return ServiceFactory.get_snapshot_service()

    @staticmethod
    def get_csv_inbound_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "CSVInboundService":
        return ServiceFactory.get_csv_inbound_service(config, force_user, offline)

    @staticmethod
    def get_screening_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ScreeningService":
        return ServiceFactory.get_screening_service(config, force_user, offline)

    @staticmethod
    def get_extraction_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ExtractionService":
        return ServiceFactory.get_extraction_service(config, force_user, offline)

    @staticmethod
    def get_import_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ImportService":
        return ServiceFactory.get_import_service(config, force_user, offline)

    @staticmethod
    def get_purge_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "PurgeService":
        return ServiceFactory.get_purge_service(config, force_user, offline)

    @staticmethod
    def get_tag_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "TagService":
        return ServiceFactory.get_tag_service(config, force_user, offline)

    @staticmethod
    def get_job_queue_service(config: Optional[ZoteroConfig] = None) -> "JobQueueService":
        return ServiceFactory.get_job_queue_service(config)

    @staticmethod
    def get_pdf_finder_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "PDFFinderService":
        return ServiceFactory.get_pdf_finder_service(config, force_user, offline)

    @staticmethod
    def get_arxiv_gateway() -> "ArxivLibGateway":
        return MetadataClientFactory.get_arxiv_gateway()

    @staticmethod
    def get_bibtex_gateway() -> "BibtexLibGateway":
        return MetadataClientFactory.get_bibtex_gateway()

    @staticmethod
    def get_ris_gateway() -> "RisLibGateway":
        return MetadataClientFactory.get_ris_gateway()

    @staticmethod
    def get_springer_csv_gateway() -> "SpringerCsvLibGateway":
        return MetadataClientFactory.get_springer_csv_gateway()

    @staticmethod
    def get_ieee_csv_gateway() -> "IeeeCsvLibGateway":
        return MetadataClientFactory.get_ieee_csv_gateway()

    @staticmethod
    def get_canonical_csv_gateway() -> "CanonicalCsvLibGateway":
        return MetadataClientFactory.get_canonical_csv_gateway()

    @staticmethod
    def get_network_gateway() -> "NetworkGateway":
        return ResolverFactory.get_network_gateway()

    @staticmethod
    def get_unpaywall_resolver(config: Optional[ZoteroConfig] = None) -> "PDFResolver":
        return ResolverFactory.get_unpaywall_resolver(config)

    @staticmethod
    def get_openalex_resolver() -> "PDFResolver":
        return ResolverFactory.get_openalex_resolver()

    @staticmethod
    def get_arxiv_resolver() -> "PDFResolver":
        return ResolverFactory.get_arxiv_resolver()

    @staticmethod
    def get_semantic_scholar_resolver(config: Optional[ZoteroConfig] = None) -> "PDFResolver":
        return ResolverFactory.get_semantic_scholar_resolver(config)

    @staticmethod
    def get_bdtd_resolver() -> "PDFResolver":
        return ResolverFactory.get_bdtd_resolver()

    @staticmethod
    def get_generic_resolvers() -> List["PDFResolver"]:
        return ResolverFactory.get_generic_resolvers()

    @staticmethod
    def get_snowball_graph_service() -> "SnowballGraphService":
        return ResolverFactory.get_snowball_graph_service()

    @staticmethod
    def get_snowball_worker(config: Optional[ZoteroConfig] = None) -> "SnowballDiscoveryWorker":
        return ResolverFactory.get_snowball_worker(config)

    @staticmethod
    def get_snowball_ingestion_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SnowballIngestionService":
        return ResolverFactory.get_snowball_ingestion_service(config, force_user, offline)

    @staticmethod
    def get_verify_service() -> "VerifyService":
        return ServiceFactory.get_verify_service()

    @staticmethod
    def get_vector_repository(config: Optional[ZoteroConfig] = None) -> "VectorRepository":
        return AIProviderFactory.get_vector_repository(config)

    @staticmethod
    def get_embedding_provider(config: Optional[ZoteroConfig] = None) -> "EmbeddingProvider":
        return AIProviderFactory.get_embedding_provider(config)

    @staticmethod
    def get_slr_orchestrator(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SLROrchestrator":
        return ServiceFactory.get_slr_orchestrator(config, force_user, offline)

    @staticmethod
    def get_slr_status_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SLRStatusService":
        return ServiceFactory.get_slr_status_service(config, force_user, offline)

    @staticmethod
    def get_citation_service() -> "CitationService":
        return ServiceFactory.get_citation_service()

    @staticmethod
    def get_llm_provider(config: Optional[ZoteroConfig] = None) -> Optional["LLMProvider"]:
        return AIProviderFactory.get_llm_provider(config)

    @staticmethod
    def get_rag_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "RAGService":
        return AIProviderFactory.get_rag_service(config, force_user, offline)

    @staticmethod
    def get_speech_service(config: Optional[ZoteroConfig] = None) -> "SpeechService":
        return AIProviderFactory.get_speech_service(config)
