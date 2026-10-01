import logging
from typing import Any, Dict, Optional, Tuple, cast

from zotero_cli.core.config import ZoteroConfig, not_configured
from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
    TagRepository,
    ZoteroGateway,
)

logger = logging.getLogger(__name__)


# The gateways are imported when first used: the Web API client pulls in
# requests, httpx and tenacity, about 60 ms that `--help` and offline runs
# don't need (Issue #433). Module attributes of the same names stay
# available (and patchable) through __getattr__.
def __getattr__(name: str) -> Any:
    if name == "ZoteroAPIClient":
        from zotero_cli.infra.zotero_api import ZoteroAPIClient

        return ZoteroAPIClient
    if name == "SqliteZoteroGateway":
        from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

        return SqliteZoteroGateway
    raise AttributeError(name)


def _gateway_class(name: str) -> Any:
    # A test may have patched the module attribute; prefer it.
    return globals().get(name) or __getattr__(name)


# Where zotero.sqlite usually is, for the offline-mode error (Issue #376).
_DATABASE_HINT = (
    "Set database_path in the [zotero] table (or ZOTERO_DATABASE_PATH) to your zotero.sqlite, "
    "usually ~/Zotero/zotero.sqlite (Windows: %USERPROFILE%\\Zotero\\zotero.sqlite)."
)

# (api key, library id) -> "user" | "group", resolved once per process.
_IMPLICIT_TYPE: Dict[Tuple[str, str], str] = {}


def _implicit_library_type(api_key: str, library_id: str) -> str:
    """The type of `library_id` when the config doesn't say (Issue #397):
    "user" if it is the key's own user ID, else "group". The docs have
    users put their user ID in ZOTERO_LIBRARY_ID, and the old "group"
    default then requested /groups/<userID>."""
    cache_key = (api_key, library_id)
    if cache_key not in _IMPLICIT_TYPE:
        try:
            identity = _gateway_class("ZoteroAPIClient").resolve_key_identity(api_key)
        except Exception as e:
            # The real request will report the problem; keep the default.
            logger.debug("Could not resolve the key's user ID: %s", e)
            return "group"
        is_user = str(identity.user_id) == str(library_id)
        _IMPLICIT_TYPE[cache_key] = "user" if is_user else "group"
        if is_user:
            logger.info(
                "library_type isn't set and %s is this key's user library: using it. "
                "Set library_type (or ZOTERO_LIBRARY_TYPE) to skip this check.",
                library_id,
            )
    return _IMPLICIT_TYPE[cache_key]


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
            from zotero_cli.core.runtime import is_offline_mode

            offline = is_offline_mode()

        if offline:
            if not config.database_path:
                raise not_configured(f"--offline needs database_path. {_DATABASE_HINT}")
            gateway = _gateway_class("SqliteZoteroGateway")(
                config.database_path,
                library_id=config.library_id,
                library_type=config.library_type,
            )
            return cast(ZoteroGateway, gateway)

        api_key = config.api_key
        if not api_key:
            raise not_configured("No Zotero API key is set.")

        library_id, library_type = RepositoryFactory.resolve_target(
            config, force_user, require_group
        )
        return cast(
            ZoteroGateway, _gateway_class("ZoteroAPIClient")(api_key, library_id, library_type)
        )

    @staticmethod
    def resolve_target(
        config: ZoteroConfig, force_user: bool = False, require_group: bool = True
    ) -> Tuple[str, str]:
        """The (library id, type) the online gateway uses, including the
        implicit type check (Issue #397)."""
        library_id, library_type = config.resolve_library_target(force_user, require_group)
        if (
            not config.library_type_set
            and not force_user
            and config.api_key
            and config.library_id
            and library_id == config.library_id
        ):
            library_type = _implicit_library_type(config.api_key, library_id)
        return library_id, library_type

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
