from typing import List, Any

from fastapi import APIRouter, Depends

from zotero_cli.api.dependencies import get_gateway
from zotero_cli.core.interfaces import ZoteroGateway

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=List[dict])
async def list_collections(
    gateway: ZoteroGateway = Depends(get_gateway),
):
    """
    Get all collections in flat structure (for now).
    """
    cols = gateway.get_all_collections()
    # Serialize
    serialized = []
    for c in cols:
        data = c.get("data", {})
        serialized.append({
            "key": c.get("key"),
            "name": data.get("name"),
            "parent": data.get("parentCollection")
        })
    return serialized
