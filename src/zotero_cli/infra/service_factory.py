from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from zotero_cli.core.config import ZoteroConfig, get_config, get_state_dir
from zotero_cli.infra.metadata_client_factory import MetadataClientFactory
from zotero_cli.infra.repository_factory import RepositoryFactory
from zotero_cli.infra.resolver_factory import ResolverFactory

if TYPE_CHECKING:
    from zotero_cli.core.interfaces import ZoteroGateway
    from zotero_cli.core.services.agent_tools import AgentTools
    from zotero_cli.core.services.attachment_service import AttachmentService
    from zotero_cli.core.services.backup_service import BackupService
    from zotero_cli.core.services.collection_service import CollectionService
    from zotero_cli.core.services.diagnostics_service import DiagnosticsService
    from zotero_cli.core.services.enrichment_service import EnrichmentService
    from zotero_cli.core.services.export_service import ExportService
    from zotero_cli.core.services.import_service import ImportService
    from zotero_cli.core.services.integrity_service import IntegrityService
    from zotero_cli.core.services.job_queue_service import JobQueueService
    from zotero_cli.core.services.merge_service import MergeService
    from zotero_cli.core.services.pdf_finder_service import PDFFinderService
    from zotero_cli.core.services.purge_service import PurgeService
    from zotero_cli.core.services.restore_service import RestoreService
    from zotero_cli.core.services.sandbox_service import SandboxService
    from zotero_cli.core.services.search_service import SearchService
    from zotero_cli.core.services.storage_service import StorageService
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
        col_repo = RepositoryFactory.get_collection_repository(config, force_user, offline=offline)
        att_repo = RepositoryFactory.get_attachment_repository(config, force_user, offline=offline)
        note_repo = RepositoryFactory.get_note_repository(config, force_user, offline=offline)
        aggregator = MetadataClientFactory.get_metadata_aggregator(config)
        from zotero_cli.core.services.attachment_service import AttachmentService

        return AttachmentService(item_repo, col_repo, att_repo, note_repo, aggregator)

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
        col_repo = RepositoryFactory.get_collection_repository(config, force_user, offline=offline)

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
        from zotero_cli.core.runtime import is_offline_mode
        from zotero_cli.infra.bxc_formatter import BxcBibliographyFormatter

        formatter = BxcBibliographyFormatter(
            offline=is_offline_mode() if offline is None else offline
        )
        return ExportService(collection_repo, bibtex_gateway, ris_gateway, formatter)

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
        col_repo = RepositoryFactory.get_collection_repository(config, force_user, offline=offline)
        arxiv_gateway = MetadataClientFactory.get_arxiv_gateway()
        aggregator = MetadataClientFactory.get_metadata_aggregator(config)
        # OpenAlex's search backs the opt-in --by-title matching (Issue #344).
        title_searcher = MetadataClientFactory.get_openalex_client(config)

        from zotero_cli.core.services.enrichment_service import EnrichmentService

        return EnrichmentService(item_repo, col_repo, arxiv_gateway, aggregator, title_searcher)

    @staticmethod
    def get_restore_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "RestoreService":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.restore_service import RestoreService

        return RestoreService(gateway, gateway, gateway, gateway)

    @staticmethod
    def get_integrity_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "IntegrityService":
        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.integrity_service import IntegrityService

        return IntegrityService(gateway, gateway)

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
    def get_search_service(gateway: "ZoteroGateway") -> "SearchService":
        from zotero_cli.core.services.search_service import SearchService

        return SearchService(gateway)

    @staticmethod
    def get_backup_service(gateway: "ZoteroGateway") -> "BackupService":
        from zotero_cli.core.services.backup_service import BackupService

        return BackupService(gateway, gateway, gateway)

    @staticmethod
    def get_storage_service(
        config: ZoteroConfig,
        gateway: "ZoteroGateway",
        notify: Optional[Callable[[str], None]] = None,
    ) -> "StorageService":
        from zotero_cli.core.services.storage_service import StorageService

        return StorageService(config, gateway, gateway, notify=notify)

    @staticmethod
    def get_agent_tools(
        describe_cli: Callable[[Optional[List[str]]], Dict[str, Any]], force_user: bool = False
    ) -> "AgentTools":
        """The tool surface behind `mcp serve` (read-only)."""
        from zotero_cli.core.services.agent_tools import AgentTools

        gateway = RepositoryFactory.get_zotero_gateway(force_user=force_user)
        collections = ServiceFactory.get_collection_service(force_user=force_user)
        export = ServiceFactory.get_export_service(force_user=force_user)
        return AgentTools(
            search=ServiceFactory.get_search_service(gateway),
            items=gateway,
            collections=gateway,
            tags=gateway,
            attachments=gateway,
            text=ServiceFactory.get_attachment_service(force_user=force_user),
            resolve_collection=collections.resolve_collection,
            format_bibliography=export.serialize_bibliography,
            describe_cli=describe_cli,
        )

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
    def get_job_queue_service(
        config: Optional[ZoteroConfig] = None, force_user: bool = False
    ) -> "JobQueueService":
        # Decouple from Zotero's main DB. Store jobs in the config directory.
        db_dir = get_state_dir()
        db_path = str(db_dir / "jobs.sqlite")

        from zotero_cli.infra.sqlite_job_repo import SqliteJobRepository

        repo = SqliteJobRepository(db_path)

        # Scope jobs to the active library (Issue #150): a config directory
        # can in principle be shared or omitted across invocations, and
        # without this, two SLR projects would silently share one job pool.
        # force_user (Issue #257) makes --user apply to this scoping too.
        resolved_config = config or get_config()
        library_id = resolved_config.resolve_scoping_id(force_user)

        from zotero_cli.core.services.job_queue_service import JobQueueService

        return JobQueueService(repo, library_id=library_id)

    @staticmethod
    def get_pdf_finder_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "PDFFinderService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        job_queue = ServiceFactory.get_job_queue_service(config, force_user)
        item_repo = RepositoryFactory.get_item_repository(config, force_user, offline=offline)
        att_repo = RepositoryFactory.get_attachment_repository(config, force_user, offline=offline)

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

        from zotero_cli.core.exceptions import ConfigurationError

        # Unconfigured, `system check` still runs and says what's missing
        # (Issue #376).
        gateway: Optional["ZoteroGateway"] = None
        gateway_error = None
        try:
            gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        except ConfigurationError as e:
            gateway_error = str(e)
        aggregator = MetadataClientFactory.get_metadata_aggregator(config)

        from zotero_cli.core.services.diagnostics_service import DiagnosticsService

        return DiagnosticsService(gateway, aggregator, config, gateway_error)

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

        from zotero_cli.core.services.sandbox_service import SandboxService

        return SandboxService(collection_repo, item_repo)
