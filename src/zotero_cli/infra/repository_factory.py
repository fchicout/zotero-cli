import re
import sys
from typing import Optional

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
    TagRepository,
    ZoteroGateway,
)
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway
from zotero_cli.infra.zotero_api import ZoteroAPIClient


class RepositoryFactory:
    """
    Constructs the core Zotero gateway (online API or offline SQLite) and the
    narrow repository interfaces (Item/Collection/Tag/Note/Attachment) that
    wrap it.
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

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroItemRepository(gateway)

    @staticmethod
    def get_collection_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> CollectionRepository:
        from zotero_cli.infra.repositories import ZoteroCollectionRepository

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroCollectionRepository(gateway)

    @staticmethod
    def get_tag_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> TagRepository:
        from zotero_cli.infra.repositories import ZoteroTagRepository

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroTagRepository(gateway)

    @staticmethod
    def get_note_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> NoteRepository:
        from zotero_cli.infra.repositories import ZoteroNoteRepository

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroNoteRepository(gateway)

    @staticmethod
    def get_attachment_repository(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> AttachmentRepository:
        from zotero_cli.infra.repositories import ZoteroAttachmentRepository

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        return ZoteroAttachmentRepository(gateway)
