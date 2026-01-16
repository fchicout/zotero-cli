import os
import sys
import re
from pathlib import Path
from typing import Optional

from zotero_cli.core.config import get_config, ZoteroConfig
from zotero_cli.infra.zotero_api import ZoteroAPIClient
from zotero_cli.infra.arxiv_lib import ArxivLibGateway
from zotero_cli.infra.bibtex_lib import BibtexLibGateway
from zotero_cli.infra.ris_lib import RisLibGateway
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
from zotero_cli.infra.crossref_api import CrossRefAPIClient
from zotero_cli.infra.semantic_scholar_api import SemanticScholarAPIClient 
from zotero_cli.infra.unpaywall_api import UnpaywallAPIClient 
from zotero_cli.client import PaperImporterClient

class GatewayFactory:
    """
    Central factory for creating Zotero and metadata gateways.
    Implements Dependency Injection pattern.
    """

    @staticmethod
    def get_zotero_gateway(config: Optional[ZoteroConfig] = None, force_user: bool = False, require_group: bool = True):
        if not config:
            from zotero_cli.core.config import get_config as main_get_config
            config = main_get_config()
            
        api_key = config.api_key
        if not api_key:
            print("Error: Zotero API Key not set.", file=sys.stderr)
            sys.exit(1)

        library_id = config.library_id
        library_type = config.library_type
        
        # Priority logic mirrored from main.py
        if force_user:
            library_id = config.user_id
            library_type = 'user'
        elif not library_id:
            if config.target_group_url:
                match = re.search(r'/groups/(\d+)', config.target_group_url)
                if not match:
                    print(f"Error: Could not extract Group ID from URL: {config.target_group_url}", file=sys.stderr)
                    sys.exit(1)
                library_id = match.group(1)
                library_type = 'group'
            elif config.user_id:
                library_id = config.user_id
                library_type = 'user'

        if not library_id:
            if require_group:
                print("Error: No target library defined.", file=sys.stderr)
                sys.exit(1)
            else:
                library_id = "0"
                library_type = 'user'

        return ZoteroAPIClient(api_key, library_id, library_type)

    @staticmethod
    def get_item_repository(config: Optional[ZoteroConfig] = None, force_user: bool = False) -> 'ItemRepository':
        from zotero_cli.infra.repositories import ZoteroItemRepository
        gateway = GatewayFactory.get_zotero_gateway(config, force_user)
        return ZoteroItemRepository(gateway)

    @staticmethod
    def get_collection_repository(config: Optional[ZoteroConfig] = None, force_user: bool = False) -> 'CollectionRepository':
        from zotero_cli.infra.repositories import ZoteroCollectionRepository
        gateway = GatewayFactory.get_zotero_gateway(config, force_user)
        return ZoteroCollectionRepository(gateway)

    @staticmethod
    def get_tag_repository(config: Optional[ZoteroConfig] = None, force_user: bool = False) -> 'TagRepository':
        from zotero_cli.infra.repositories import ZoteroTagRepository
        gateway = GatewayFactory.get_zotero_gateway(config, force_user)
        return ZoteroTagRepository(gateway)

    @staticmethod
    def get_note_repository(config: Optional[ZoteroConfig] = None, force_user: bool = False) -> 'NoteRepository':
        from zotero_cli.infra.repositories import ZoteroNoteRepository
        gateway = GatewayFactory.get_zotero_gateway(config, force_user)
        return ZoteroNoteRepository(gateway)

    @staticmethod
    def get_metadata_aggregator(config: Optional[ZoteroConfig] = None):
        if not config:
            from zotero_cli.core.config import get_config as main_get_config
            config = main_get_config()
            
        ss_client = SemanticScholarAPIClient(config.semantic_scholar_api_key) if config.semantic_scholar_api_key else SemanticScholarAPIClient()
        cr_client = CrossRefAPIClient()
        up_client = UnpaywallAPIClient(config.unpaywall_email) if config.unpaywall_email else UnpaywallAPIClient()
        
        from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
        aggregator = MetadataAggregatorService([ss_client, cr_client, up_client])
        
        # Assign attributes for compatibility with PaperImporterClient
        aggregator.semantic_scholar = ss_client
        aggregator.crossref = cr_client
        aggregator.unpaywall = up_client
        
        return aggregator

    @staticmethod
    def get_attachment_service(config: Optional[ZoteroConfig] = None, force_user: bool = False):
        if not config:
            from zotero_cli.core.config import get_config as main_get_config
            config = main_get_config()

        item_repo = GatewayFactory.get_item_repository(config, force_user)
        col_repo = GatewayFactory.get_collection_repository(config, force_user)
        att_repo = GatewayFactory.get_item_repository(config, force_user) # It also implements AttachmentRepository for now
        note_repo = GatewayFactory.get_note_repository(config, force_user)
        aggregator = GatewayFactory.get_metadata_aggregator(config)
        
        from zotero_cli.core.services.attachment_service import AttachmentService
        return AttachmentService(item_repo, col_repo, att_repo, note_repo, aggregator)

    @staticmethod
    def get_collection_service(config: Optional[ZoteroConfig] = None, force_user: bool = False):
        if not config:
            from zotero_cli.core.config import get_config as main_get_config
            config = main_get_config()

        item_repo = GatewayFactory.get_item_repository(config, force_user)
        col_repo = GatewayFactory.get_collection_repository(config, force_user)
        
        from zotero_cli.core.services.collection_service import CollectionService
        return CollectionService(item_repo, col_repo)

    @staticmethod
    def get_screening_service(config: Optional[ZoteroConfig] = None, force_user: bool = False):
        if not config:
            from zotero_cli.core.config import get_config as main_get_config
            config = main_get_config()

        item_repo = GatewayFactory.get_item_repository(config, force_user)
        col_repo = GatewayFactory.get_collection_repository(config, force_user)
        note_repo = GatewayFactory.get_note_repository(config, force_user)
        tag_repo = GatewayFactory.get_tag_repository(config, force_user)
        col_service = GatewayFactory.get_collection_service(config, force_user)
        
        from zotero_cli.core.services.screening_service import ScreeningService
        return ScreeningService(item_repo, col_repo, note_repo, tag_repo, col_service)

    @staticmethod
    def get_paper_importer(config: Optional[ZoteroConfig] = None, force_user: bool = False):
        if not config:
            from zotero_cli.core.config import get_config as main_get_config
            config = main_get_config()

        zotero_gateway = GatewayFactory.get_zotero_gateway(config, force_user)
        aggregator = GatewayFactory.get_metadata_aggregator(config)
        
        # Format gateways
        arxiv_gateway = ArxivLibGateway()
        bibtex_gateway = BibtexLibGateway()
        ris_gateway = RisLibGateway()
        springer_csv_gateway = SpringerCsvLibGateway()
        ieee_csv_gateway = IeeeCsvLibGateway()

        return PaperImporterClient(
            zotero_gateway,
            arxiv_gateway,
            bibtex_gateway,
            ris_gateway,
            springer_csv_gateway,
            ieee_csv_gateway,
            aggregator.semantic_scholar,
            aggregator.crossref,
            aggregator.unpaywall
        )
