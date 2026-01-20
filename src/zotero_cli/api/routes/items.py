from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from zotero_cli.api.dependencies import get_gateway
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ZoteroQuery
from zotero_cli.core.zotero_item import ZoteroItem

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=List[dict])
async def list_items(
    q: Optional[str] = Query(None, description="Search query"),
    limit: int = Query(25, ge=1, le=100),
    sort: str = Query("date", description="Sort field"),
    direction: str = Query("desc", description="Sort direction (asc/desc)"),
    gateway: ZoteroGateway = Depends(get_gateway),
):
    query = ZoteroQuery(q=q, sort=sort, direction=direction)
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
            items.append({
                "key": item.key,
                "title": item.title,
                "creators": item.authors,
                "date": item.date,
                "itemType": item.item_type,
                "has_pdf": item.has_pdf
            })
        except StopIteration:
            break
            
    return items


@router.get("/{key}", response_model=dict)
async def get_item(
    key: str,
    gateway: ZoteroGateway = Depends(get_gateway),
):
    item = gateway.get_item(key)
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
        "raw": item.raw_data
    }
