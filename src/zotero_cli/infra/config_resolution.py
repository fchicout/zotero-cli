from typing import Optional

from zotero_cli.core.config import ZoteroConfig


def resolve_config(config: Optional[ZoteroConfig]) -> ZoteroConfig:
    """`config` if given, else the loaded configuration. Looked up at call time, so a
    patched `zotero_cli.core.config.get_config` is honoured."""
    if config:
        return config
    from zotero_cli.core import config as config_module

    return config_module.get_config()
