from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from zotero_cli.api.dependencies import get_gateway
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ZoteroQuery

router = APIRouter(prefix="/items", tags=["items"])


def _list_items_sync(gateway: ZoteroGateway, query: ZoteroQuery, limit: int) -> List[Dict[str, Any]]:
    # Zotero API search pagination is tricky with search_items generator.
    # We'll fetch from the iterator up to limit.
    items = []

    # search_items returns an Iterator[ZoteroItem]
    # We need to respect the limit here manually since ZoteroQuery logic
    # might apply limit at API level if implemented, but ZoteroQuery object doesn't carry 'limit' itself
    # in the current definition (checking models.py... it doesn't have limit).
    # wait, ZoteroAPIClient._paginate_items hardcodes limit=100.

    # We should probably pass 'limit' to search_items if possible, but the interface definition
    # of search_items(query: ZoteroQuery) doesn't take extra args.
    # So we slice the iterator.

    iterator = gateway.search_items(query)

    for _ in range(limit):
        try:
            item = next(iterator)
            # Serialize basic data
            items.append(
                {
                    "key": item.key,
                    "title": item.title,
                    "creators": item.authors,
                    "date": item.date,
                    "itemType": item.item_type,
                    "has_pdf": item.has_pdf,
                }
            )
        except StopIteration:
            break

    return items


@router.get("", response_model=List[dict])
async def list_items(
    gateway: Annotated[ZoteroGateway, Depends(get_gateway)],
    q: Annotated[Optional[str], Query(description="Search query")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    sort: Annotated[str, Query(description="Sort field")] = "date",
    direction: Annotated[str, Query(description="Sort direction (asc/desc)")] = "desc",
) -> List[Dict[str, Any]]:
    query = ZoteroQuery(q=q, sort=sort, direction=direction)
    # Issue #269: gateway.search_items/get_item are synchronous (blocking
    # requests/sqlite3 calls) - running them directly in an async def route
    # blocks the whole single-threaded event loop for every concurrent
    # client, including /health, for the duration of the call. Offload to
    # FastAPI/Starlette's threadpool instead.
    return await run_in_threadpool(_list_items_sync, gateway, query, limit)


@router.get("/{key}", response_model=dict, responses={404: {"description": "Item not found"}})
async def get_item(
    key: str,
    gateway: Annotated[ZoteroGateway, Depends(get_gateway)],
) -> Dict[str, Any]:
    item = await run_in_threadpool(gateway.get_item, key)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return {
        "key": item.key,
        "title": item.title,
        "abstract": item.abstract,
        "creators": item.authors,
        "date": item.date,
        "url": item.url,
        "doi": item.doi,
        "raw": item.raw_data,
    }
