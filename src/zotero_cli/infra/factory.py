import re
import sys
from typing import TYPE_CHECKING, List, Optional

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
    TagRepository,
    ZoteroGateway,
)
from zotero_cli.infra.arxiv_lib import ArxivLibGateway
from zotero_cli.infra.bibtex_lib import BibtexLibGateway
from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway
from zotero_cli.infra.crossref_api import CrossRefAPIClient
from zotero_cli.infra.dblp_api import DBLPAPIClient
from zotero_cli.infra.eric_api import ERICAPIClient
from zotero_cli.infra.hal_api import HALAPIClient
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
from zotero_cli.infra.inspire_hep_api import InspireHEPAPIClient
from zotero_cli.infra.openalex_api import OpenAlexAPIClient
from zotero_cli.infra.pubmed_api import PubMedAPIClient
from zotero_cli.infra.ris_lib import RisLibGateway
from zotero_cli.infra.semantic_scholar_api import SemanticScholarAPIClient
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway
from zotero_cli.infra.unpaywall_api import UnpaywallAPIClient
from zotero_cli.infra.zbmath_api import zbMATHAPIClient
from zotero_cli.infra.zotero_api import ZoteroAPIClient

if TYPE_CHECKING:
    from zotero_cli.core.interfaces import (
        EmbeddingProvider,
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
    from zotero_cli.core.services.slr.csv_inbound import CSVInboundService
    from zotero_cli.core.services.slr.integrity import IntegrityService
    from zotero_cli.core.services.slr.snapshot import SnapshotService
    from zotero_cli.core.services.snowball_graph import SnowballGraphService
    from zotero_cli.core.services.snowball_ingestion import SnowballIngestionService
    from zotero_cli.core.services.snowball_worker import SnowballDiscoveryWorker
    from zotero_cli.core.services.tag_service import TagService
    from zotero_cli.core.services.transfer_service import TransferService
    from zotero_cli.core.services.verify_service import VerifyService


class GatewayFactory:
    """
    Central factory for creating Zotero and metadata gateways.
    Implements Dependency Injection pattern.
    """

    @staticmethod
    def get_zotero_gateway(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        require_group: bool = True,
        offline: Optional[bool] = None,
    ) -> "ZoteroGateway":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        if offline is None:
            try:
                from zotero_cli.cli.main import OFFLINE_MODE

                offline = OFFLINE_MODE
            except ImportError:
                offline = False

        if offline:
            if not config.database_path:
                print("Error: Offline mode requires 'database_path' in config.", file=sys.stderr)
                sys.exit(1)
            return SqliteZoteroGateway(config.database_path)

        api_key = config.api_key
        if not api_key:
            print("Error: Zotero API Key not set.", file=sys.stderr)
            sys.exit(1)

        library_id = config.library_id
        library_type = config.library_type

        # Priority logic mirrored from main.py
        if force_user:
            library_id = config.user_id
            library_type = "user"
        elif not library_id:
            if config.target_group_url:
                match = re.search(r"/groups/(\d+)", config.target_group_url)
                if not match:
                    print(
                        f"Error: Could not extract Group ID from URL: {config.target_group_url}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                library_id = match.group(1)
                library_type = "group"
            elif config.user_id:
                library_id = config.user_id
                library_type = "user"

        if not library_id:
            if require_group:
                print("Error: No target library defined.", file=sys.stderr)
                sys.exit(1)
            else:
                library_id = "0"
                library_type = "user"

        return ZoteroAPIClient(api_key, library_id, library_type)

    @staticmethod
    def get_item_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> ItemRepository:
        from zotero_cli.infra.repositories import ZoteroItemRepository

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroItemRepository(gateway)

    @staticmethod
    def get_collection_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> CollectionRepository:
        from zotero_cli.infra.repositories import ZoteroCollectionRepository

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroCollectionRepository(gateway)

    @staticmethod
    def get_tag_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> TagRepository:
        from zotero_cli.infra.repositories import ZoteroTagRepository

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroTagRepository(gateway)

    @staticmethod
    def get_note_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> NoteRepository:
        from zotero_cli.infra.repositories import ZoteroNoteRepository

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroNoteRepository(gateway)

    @staticmethod
    def get_attachment_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> AttachmentRepository:
        from zotero_cli.infra.repositories import ZoteroAttachmentRepository

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroAttachmentRepository(gateway)

    @staticmethod
    def get_openalex_client(config: Optional[ZoteroConfig] = None) -> OpenAlexAPIClient:
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()
        return OpenAlexAPIClient(email=config.unpaywall_email)

    @staticmethod
    def get_pubmed_client(config: Optional[ZoteroConfig] = None) -> PubMedAPIClient:
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()
        return PubMedAPIClient(api_key=config.ncbi_api_key)

    @staticmethod
    def get_zbmath_client() -> zbMATHAPIClient:
        return zbMATHAPIClient()

    @staticmethod
    def get_eric_client() -> ERICAPIClient:
        return ERICAPIClient()

    @staticmethod
    def get_dblp_client() -> DBLPAPIClient:
        return DBLPAPIClient()

    @staticmethod
    def get_hal_client() -> HALAPIClient:
        return HALAPIClient()

    @staticmethod
    def get_inspire_hep_client() -> InspireHEPAPIClient:
        return InspireHEPAPIClient()

    @staticmethod
    def get_metadata_aggregator(
        config: Optional[ZoteroConfig] = None,
    ) -> "MetadataAggregatorService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        ss_client = (
            SemanticScholarAPIClient(config.semantic_scholar_api_key)
            if config.semantic_scholar_api_key
            else SemanticScholarAPIClient()
        )
        cr_client = CrossRefAPIClient()
        up_client = (
            UnpaywallAPIClient(config.unpaywall_email)
            if config.unpaywall_email
            else UnpaywallAPIClient()
        )
        oa_client = GatewayFactory.get_openalex_client(config)
        pm_client = GatewayFactory.get_pubmed_client(config)
        zm_client = GatewayFactory.get_zbmath_client()
        eric_client = GatewayFactory.get_eric_client()
        hal_client = GatewayFactory.get_hal_client()
        ih_client = GatewayFactory.get_inspire_hep_client()
        dblp_client = GatewayFactory.get_dblp_client()

        from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService

        aggregator = MetadataAggregatorService(
            [
                ss_client,
                cr_client,
                up_client,
                oa_client,
                pm_client,
                zm_client,
                eric_client,
                hal_client,
                ih_client,
                dblp_client,
            ]
        )

        # Assign attributes for compatibility with PaperImporterClient
        aggregator.semantic_scholar = ss_client
        aggregator.crossref = cr_client
        aggregator.unpaywall = up_client
        aggregator.openalex = oa_client
        aggregator.pubmed = pm_client
        aggregator.zbmath = zm_client
        aggregator.eric = eric_client
        aggregator.hal = hal_client
        aggregator.inspire_hep = ih_client
        aggregator.dblp = dblp_client

        return aggregator

    @staticmethod
    def get_attachment_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "AttachmentService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        item_repo = GatewayFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = GatewayFactory.get_collection_repository(config, force_user, offline=offline)
        att_repo = GatewayFactory.get_attachment_repository(config, force_user, offline=offline)
        note_repo = GatewayFactory.get_note_repository(config, force_user, offline=offline)
        aggregator = GatewayFactory.get_metadata_aggregator(config)
        purge_service = GatewayFactory.get_purge_service(config, force_user, offline=offline)

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

        item_repo = GatewayFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = GatewayFactory.get_collection_repository(config, force_user, offline=offline)

        from zotero_cli.core.services.collection_service import CollectionService

        return CollectionService(item_repo, col_repo)

    @staticmethod
    def get_export_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ExportService":
        from zotero_cli.core.services.export_service import ExportService

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        bibtex_gateway = GatewayFactory.get_bibtex_gateway()
        ris_gateway = GatewayFactory.get_ris_gateway()
        sdb_service = GatewayFactory.get_sdb_service(config, force_user, offline=offline)
        return ExportService(gateway, bibtex_gateway, ris_gateway, sdb_service)

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

        item_repo = GatewayFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = GatewayFactory.get_collection_repository(config, force_user, offline=offline)
        arxiv_gateway = GatewayFactory.get_arxiv_gateway()

        from zotero_cli.core.services.enrichment_service import EnrichmentService

        return EnrichmentService(item_repo, col_repo, arxiv_gateway)

    @staticmethod
    def get_sdb_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "SDBService":
        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.sdb.sdb_service import SDBService

        return SDBService(gateway)

    @staticmethod
    def get_audit_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "AuditService":
        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.audit_service import AuditService

        return AuditService(gateway)

    @staticmethod
    def get_restore_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "RestoreService":
        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        from zotero_cli.core.services.restore_service import RestoreService

        return RestoreService(gateway)

    @staticmethod
    def get_integrity_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "IntegrityService":
        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
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
        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
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

        item_repo = GatewayFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = GatewayFactory.get_collection_repository(config, force_user, offline=offline)
        note_repo = GatewayFactory.get_note_repository(config, force_user, offline=offline)
        tag_repo = GatewayFactory.get_tag_repository(config, force_user, offline=offline)
        col_service = GatewayFactory.get_collection_service(config, force_user, offline=offline)

        from zotero_cli.core.services.screening_service import ScreeningService

        return ScreeningService(item_repo, col_repo, note_repo, tag_repo, col_service)

    @staticmethod
    def get_extraction_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "ExtractionService":
        note_repo = GatewayFactory.get_note_repository(config, force_user, offline=offline)
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

        item_repo = GatewayFactory.get_item_repository(config, force_user, offline=offline)
        col_service = GatewayFactory.get_collection_service(config, force_user, offline=offline)

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

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)

        from zotero_cli.core.services.purge_service import PurgeService

        return PurgeService(gateway)

    @staticmethod
    def get_tag_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "TagService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        purge_service = GatewayFactory.get_purge_service(config, force_user, offline=offline)

        from zotero_cli.core.services.tag_service import TagService

        return TagService(gateway, purge_service)

    @staticmethod
    def get_job_queue_service(config: Optional[ZoteroConfig] = None) -> "JobQueueService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        # Decouple from Zotero's main DB. Store jobs in the config directory.
        from zotero_cli.core.config import get_config_path

        config_path = get_config_path()
        if config_path:
            db_dir = config_path.parent
        else:
            # Fallback if config path isn't set (e.g. during specific test setups)
            import os
            from pathlib import Path

            if os.name == "nt":
                base = Path(os.environ.get("APPDATA", "~")).expanduser()
            else:
                base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
            db_dir = base / "zotero-cli"

        # Ensure directory exists
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

        job_queue = GatewayFactory.get_job_queue_service(config)
        item_repo = GatewayFactory.get_item_repository(config, force_user, offline=offline)
        att_repo = GatewayFactory.get_attachment_repository(config, force_user, offline=offline)

        # Build Resolver Chain
        resolvers = [
            GatewayFactory.get_unpaywall_resolver(config),
            GatewayFactory.get_openalex_resolver(),
            GatewayFactory.get_arxiv_resolver(),
            GatewayFactory.get_semantic_scholar_resolver(config),
        ]
        # Add YAML-configured scrapers
        resolvers.extend(GatewayFactory.get_generic_resolvers())

        from zotero_cli.core.services.pdf_finder_service import PDFFinderService

        return PDFFinderService(job_queue, item_repo, att_repo, resolvers)

    @staticmethod
    def get_arxiv_gateway() -> ArxivLibGateway:
        return ArxivLibGateway()

    @staticmethod
    def get_bibtex_gateway() -> BibtexLibGateway:
        return BibtexLibGateway()

    @staticmethod
    def get_ris_gateway() -> RisLibGateway:
        return RisLibGateway()

    @staticmethod
    def get_springer_csv_gateway() -> SpringerCsvLibGateway:
        return SpringerCsvLibGateway()

    @staticmethod
    def get_ieee_csv_gateway() -> IeeeCsvLibGateway:
        return IeeeCsvLibGateway()

    @staticmethod
    def get_canonical_csv_gateway() -> CanonicalCsvLibGateway:
        return CanonicalCsvLibGateway()

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

        gateway = GatewayFactory.get_network_gateway()
        return UnpaywallResolver(gateway, email=config.unpaywall_email)

    @staticmethod
    def get_openalex_resolver() -> "PDFResolver":
        from zotero_cli.core.services.resolvers.openalex import OpenAlexResolver

        client = GatewayFactory.get_openalex_client()
        return OpenAlexResolver(client)

    @staticmethod
    def get_arxiv_resolver() -> "PDFResolver":
        from zotero_cli.core.services.resolvers.arxiv import ArXivResolver

        gateway = GatewayFactory.get_network_gateway()
        return ArXivResolver(gateway)

    @staticmethod
    def get_semantic_scholar_resolver(config: Optional[ZoteroConfig] = None) -> "PDFResolver":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.services.resolvers.semantic_scholar import SemanticScholarResolver

        gateway = GatewayFactory.get_network_gateway()
        return SemanticScholarResolver(gateway, api_key=config.semantic_scholar_api_key)

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

            gateway = GatewayFactory.get_network_gateway()

            return [GenericScraperResolver(gateway, cfg) for cfg in resolvers_config]
        except Exception as e:
            print(
                f"Warning: Failed to load generic resolvers from {yaml_path}: {e}", file=sys.stderr
            )
            return []

    @staticmethod
    def get_snowball_graph_service() -> "SnowballGraphService":
        from zotero_cli.core.config import get_config_path

        config_path = get_config_path()

        if config_path:
            db_dir = config_path.parent
        else:
            import os
            from pathlib import Path

            if os.name == "nt":
                base = Path(os.environ.get("APPDATA", "~")).expanduser()
            else:
                base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
            db_dir = base / "zotero-cli"

        db_dir.mkdir(parents=True, exist_ok=True)
        storage_path = db_dir / "discovery_graph.json"

        from zotero_cli.core.services.snowball_graph import SnowballGraphService

        return SnowballGraphService(storage_path)

    @staticmethod
    def get_snowball_worker(config: Optional[ZoteroConfig] = None) -> "SnowballDiscoveryWorker":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        gateway = GatewayFactory.get_network_gateway()
        graph_service = GatewayFactory.get_snowball_graph_service()
        job_queue = GatewayFactory.get_job_queue_service(config)

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

        graph_service = GatewayFactory.get_snowball_graph_service()
        metadata_service = GatewayFactory.get_metadata_aggregator(config)
        item_repo = GatewayFactory.get_item_repository(config, force_user, offline=offline)
        col_repo = GatewayFactory.get_collection_repository(config, force_user, offline=offline)

        from zotero_cli.core.services.duplicate_service import DuplicateFinder

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        duplicate_finder = DuplicateFinder(gateway)

        from zotero_cli.core.services.snowball_ingestion import SnowballIngestionService

        return SnowballIngestionService(
            graph_service, metadata_service, item_repo, col_repo, duplicate_finder
        )

    @staticmethod
    def get_verify_service() -> "VerifyService":
        from zotero_cli.core.services.verify_service import VerifyService

        return VerifyService()

    @staticmethod
    def get_vector_repository(config: Optional[ZoteroConfig] = None) -> "VectorRepository":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.config import get_config_path

        config_path = get_config_path()
        if config_path:
            db_dir = config_path.parent
        else:
            import os
            from pathlib import Path

            if os.name == "nt":
                base = Path(os.environ.get("APPDATA", "~")).expanduser()
            else:
                base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
            db_dir = base / "zotero-cli"

        db_dir.mkdir(parents=True, exist_ok=True)

        # Use library_id or default name to isolate projects
        library_suffix = config.library_id if config and config.library_id else "default"
        db_path = str(db_dir / f"vector_store_{library_suffix}.sqlite")

        from zotero_cli.infra.sqlite_vector_repo import SQLiteVectorRepository

        return SQLiteVectorRepository(db_path)

    @staticmethod
    def get_embedding_provider(config: Optional[ZoteroConfig] = None) -> "EmbeddingProvider":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.services.embedding_provider import (
            GeminiEmbeddingProvider,
            MockEmbeddingProvider,
            OpenAIEmbeddingProvider,
        )

        if config.gemini_api_key:
            return GeminiEmbeddingProvider(config.gemini_api_key)

        if config.openai_api_key:
            return OpenAIEmbeddingProvider(config.openai_api_key)

        return MockEmbeddingProvider()

    @staticmethod
    def get_rag_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "RAGService":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        gateway = GatewayFactory.get_zotero_gateway(config, force_user, offline=offline)
        vector_repo = GatewayFactory.get_vector_repository(config)
        embedding_provider = GatewayFactory.get_embedding_provider(config)
        attachment_service = GatewayFactory.get_attachment_service(
            config, force_user, offline=offline
        )

        from zotero_cli.core.services.rag_service import FixedSizeChunker, RAGServiceBase

        return RAGServiceBase(
            gateway,
            vector_repo,
            embedding_provider,
            attachment_service,
            text_splitter=FixedSizeChunker(chunk_size=1000),
        )
