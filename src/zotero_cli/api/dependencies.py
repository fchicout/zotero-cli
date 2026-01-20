from typing import Optional

from fastapi import Depends

from zotero_cli.core.config import get_config
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.infra.factory import GatewayFactory

# Global state for the gateway to persist across requests
_GATEWAY: Optional[ZoteroGateway] = None


def get_gateway() -> ZoteroGateway:
    """
    Dependency to retrieve the ZoteroGateway instance.
    Raises RuntimeError if the gateway hasn't been initialized by the startup event.
    """
    if _GATEWAY is None:
        # Fallback for dev/testing: try to load from default config
        try:
            config = get_config()
            return GatewayFactory.get_zotero_gateway(config)
        except Exception:
             raise RuntimeError("ZoteroGateway is not initialized.")
    return _GATEWAY


def set_gateway_instance(gateway: ZoteroGateway):
    """
    Sets the global gateway instance. Should be called on app startup.
    """
    global _GATEWAY
    _GATEWAY = gateway
