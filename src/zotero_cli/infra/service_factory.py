from typing import TYPE_CHECKING, Optional

from zotero_cli.core.config import ZoteroConfig, get_storage_dir
from zotero_cli.infra.metadata_client_factory import MetadataClientFactory
from zotero_cli.infra.repository_factory import RepositoryFactory
from zotero_cli.infra.resolver_factory import ResolverFactory

if TYPE_CHECKING:
    from zotero_cli.core.services.attachment_service import AttachmentService
    from zotero_cli.core.services.audit_service import AuditService
    from zotero_cli.core.services.collection_service import CollectionService
    from zotero_cli.core.services.diagnostics_service import DiagnosticsService
    from zotero_cli.core.services.enrichment_service import EnrichmentService
    from zotero_cli.core.services.export_service import ExportService
    from zotero_cli.core.services.extraction_service import ExtractionService
    from zotero_cli.core.services.import_service import ImportService
    from zotero_cli.core.services.job_queue_service import JobQueueService
    from zotero_cli.core.services.merge_service import MergeService
    from zotero_cli.core.services.pdf_finder_service import PDFFinderService
    from zotero_cli.core.services.purge_service import PurgeService
    from zotero_cli.core.services.restore_service import RestoreService
    from zotero_cli.core.services.sandbox_service import SandboxService
    from zotero_cli.core.services.screening_service import ScreeningService
    from zotero_cli.core.services.sdb.sdb_service import SDBService
    from zotero_cli.core.services.slr.citation_service import CitationService
    from zotero_cli.core.services.slr.csv_inbound import CSVInboundService
    from zotero_cli.core.services.slr.dedupe_service import SLRDedupeService
    from zotero_cli.core.services.slr.integrity import IntegrityService
    from zotero_cli.core.services.slr.orchestrator import SLROrchestrator
    from zotero_cli.core.services.slr.snapshot import SnapshotService
    from zotero_cli.core.services.slr.status_service import SLRStatusService
    from zotero_cli.core.services.tag_service import TagService
    from zotero_cli.core.services.transfer_service import TransferService
    from zotero_cli.core.services.verify_service import VerifyService


class ServiceFactory:
    """
    Constructs the domain services (SLR workflow, import/export, screening,
    purge, job queue, PDF finding, etc.) by composing the narrow repositories
    from RepositoryFactory with the external clients from MetadataClientFactory
    and the resolver chain from ResolverFactory.
    """

    @staticmethod
    def get_attachment_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "AttachmentService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = RepositoryFactory.get_collection_repository(
            config, force_user, offline=offline
        )
        att_repo = RepositoryFactory.get_attachment_repository(
            config, force_user, offline=offline
        )
        note_repo = RepositoryFactory.get_note_repository(config, force_user, offline=offline)
        aggregator = MetadataClientFactory.get_metadata_aggregator(config)
        purge_service = ServiceFactory.get_purge_service(config, force_user, offline=offline)

        from zotero_cli.core.services.attachment_service import AttachmentService

        return AttachmentService(
            item_repo, col_repo, att_repo, note_repo, aggregator, purge_service
        )

    @staticmethod
    def get_collection_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "CollectionService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = RepositoryFactory.get_collection_repository(
            config, force_user, offline=offline
        )

        from zotero_cli.core.services.collection_service import CollectionService

        return CollectionService(item_repo, col_repo)

    @staticmethod
    def get_export_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ExportService":
        from zotero_cli.core.services.export_service import ExportService

        collection_repo = RepositoryFactory.get_collection_repository(
            config, force_user, offline=offline
        )
        bibtex_gateway = MetadataClientFactory.get_bibtex_gateway()
        ris_gateway = MetadataClientFactory.get_ris_gateway()
        sdb_service = ServiceFactory.get_sdb_service(config, force_user, offline=offline)
        return ExportService(collection_repo, bibtex_gateway, ris_gateway, sdb_service)

    @staticmethod
    def get_transfer_service() -> "TransferService":
        from zotero_cli.core.services.transfer_service import TransferService

        return TransferService()

    @staticmethod
    def get_enrichment_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "EnrichmentService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = RepositoryFactory.get_collection_repository(
            config, force_user, offline=offline
        )
        arxiv_gateway = MetadataClientFactory.get_arxiv_gateway()

        from zotero_cli.core.services.enrichment_service import EnrichmentService

        return EnrichmentService(item_repo, col_repo, arxiv_gateway)

    @staticmethod
    def get_sdb_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SDBService":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.sdb.sdb_service import SDBService

        return SDBService(gateway)

    @staticmethod
    def get_audit_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "AuditService":
        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        from zotero_cli.core.services.audit_service import AuditService

        return AuditService(item_repo)

    @staticmethod
    def get_restore_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "RestoreService":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        orchestrator = ServiceFactory.get_slr_orchestrator(config, force_user, offline=offline)
        from zotero_cli.core.services.restore_service import RestoreService

        return RestoreService(gateway, orchestrator)

    @staticmethod
    def get_integrity_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "IntegrityService":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.slr.integrity import IntegrityService

        return IntegrityService(gateway)

    @staticmethod
    def get_snapshot_service() -> "SnapshotService":
        from zotero_cli.core.services.slr.snapshot import SnapshotService

        return SnapshotService()

    @staticmethod
    def get_csv_inbound_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "CSVInboundService":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.slr.csv_inbound import CSVInboundService

        return CSVInboundService(gateway)

    @staticmethod
    def get_screening_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ScreeningService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = RepositoryFactory.get_collection_repository(
            config, force_user, offline=offline
        )
        note_repo = RepositoryFactory.get_note_repository(config, force_user, offline=offline)
        tag_repo = RepositoryFactory.get_tag_repository(config, force_user, offline=offline)
        col_service = ServiceFactory.get_collection_service(config, force_user, offline=offline)

        from zotero_cli.core.services.screening_service import ScreeningService

        return ScreeningService(item_repo, col_repo, note_repo, tag_repo, col_service)

    @staticmethod
    def get_extraction_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ExtractionService":
        note_repo = RepositoryFactory.get_note_repository(config, force_user, offline=offline)
        from zotero_cli.core.services.extraction_service import ExtractionService

        return ExtractionService(note_repo)

    @staticmethod
    def get_import_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ImportService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        col_service = ServiceFactory.get_collection_service(config, force_user, offline=offline)

        from zotero_cli.core.services.import_service import ImportService

        return ImportService(item_repo, col_service)

    @staticmethod
    def get_purge_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "PurgeService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)

        from zotero_cli.core.services.purge_service import PurgeService

        return PurgeService(gateway)

    @staticmethod
    def get_merge_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "MergeService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        note_repo = RepositoryFactory.get_note_repository(config, force_user, offline=offline)

        from zotero_cli.core.services.merge_service import MergeService

        return MergeService(item_repo, note_repo)

    @staticmethod
    def get_tag_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "TagService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        tag_repo = RepositoryFactory.get_tag_repository(config, force_user, offline=offline)
        purge_service = ServiceFactory.get_purge_service(config, force_user, offline=offline)

        from zotero_cli.core.services.tag_service import TagService

        return TagService(item_repo, tag_repo, purge_service)

    @staticmethod
    def get_job_queue_service(config: Optional[ZoteroConfig] = None) -> "JobQueueService":
        # Decouple from Zotero's main DB. Store jobs in the config directory.
        db_dir = get_storage_dir()
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(db_dir / "jobs.sqlite")

        from zotero_cli.infra.sqlite_repo import SqliteJobRepository

        repo = SqliteJobRepository(db_path)

        from zotero_cli.core.services.job_queue_service import JobQueueService

        return JobQueueService(repo)

    @staticmethod
    def get_pdf_finder_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "PDFFinderService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        job_queue = ServiceFactory.get_job_queue_service(config)
        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        att_repo = RepositoryFactory.get_attachment_repository(
            config, force_user, offline=offline
        )

        # Build Resolver Chain
        resolvers = [
            ResolverFactory.get_unpaywall_resolver(config),
            ResolverFactory.get_openalex_resolver(),
            ResolverFactory.get_arxiv_resolver(),
            ResolverFactory.get_semantic_scholar_resolver(config),
            ResolverFactory.get_bdtd_resolver(),
        ]
        # Add YAML-configured scrapers
        resolvers.extend(ResolverFactory.get_generic_resolvers())

        from zotero_cli.core.services.pdf_finder_service import PDFFinderService

        return PDFFinderService(job_queue, item_repo, att_repo, resolvers)

    @staticmethod
    def get_verify_service() -> "VerifyService":
        from zotero_cli.core.services.verify_service import VerifyService

        return VerifyService()

    @staticmethod
    def get_diagnostics_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "DiagnosticsService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        aggregator = MetadataClientFactory.get_metadata_aggregator(config)

        from zotero_cli.infra.ai_provider_factory import AIProviderFactory

        llm_provider = AIProviderFactory.get_llm_provider(config)
        embedding_provider = AIProviderFactory.get_embedding_provider(config)

        from zotero_cli.core.services.diagnostics_service import DiagnosticsService

        return DiagnosticsService(gateway, aggregator, llm_provider, embedding_provider, config)

    @staticmethod
    def get_sandbox_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SandboxService":
        collection_repo = RepositoryFactory.get_collection_repository(
            config, force_user, offline=offline
        )
        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        note_repo = RepositoryFactory.get_note_repository(config, force_user, offline=offline)

        from zotero_cli.core.services.sandbox_service import SandboxService

        return SandboxService(collection_repo, item_repo, note_repo)

    @staticmethod
    def get_slr_orchestrator(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SLROrchestrator":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.slr.orchestrator import SLROrchestrator

        return SLROrchestrator(gateway)

    @staticmethod
    def get_slr_dedupe_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SLRDedupeService":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        merge_service = ServiceFactory.get_merge_service(config, force_user, offline=offline)
        sdb_service = ServiceFactory.get_sdb_service(config, force_user, offline=offline)
        orchestrator = ServiceFactory.get_slr_orchestrator(config, force_user, offline=offline)

        from zotero_cli.core.services.duplicate_service import DuplicateFinder
        from zotero_cli.core.services.slr.dedupe_service import SLRDedupeService

        duplicate_finder = DuplicateFinder(gateway)
        return SLRDedupeService(gateway, duplicate_finder, merge_service, sdb_service, orchestrator)

    @staticmethod
    def get_slr_status_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SLRStatusService":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        orchestrator = ServiceFactory.get_slr_orchestrator(config, force_user, offline=offline)
        from zotero_cli.core.services.slr.status_service import SLRStatusService

        return SLRStatusService(gateway, orchestrator)

    @staticmethod
    def get_citation_service() -> "CitationService":
        from zotero_cli.core.services.slr.citation_service import CitationService

        return CitationService()
