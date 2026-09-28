"""
The children (notes, attachments) of many parents at once (Issues #425, #441).

Commands that look at every paper's SDB notes or PDFs used to make one
`get_item_children` request per paper: 5,021 requests for a 5,000-paper
`slr report status`. This module picks the cheapest way to get them all:

- offline, the SQLite gateway answers in one query (`get_children_by_parent`);
- online, one library-wide scan of the child type costs ceil(total / 100)
  pages, so it is used only when that is fewer requests than one per parent.
  The total comes from one `limit=1` request. A fixed threshold (purge used
  "more than 2") made a 3-item purge page through 35k attachments;
- anything else (including test doubles) falls back to one lookup per parent.
"""

import logging
import math
from typing import Any, Dict, Iterable, List, Optional

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ZoteroQuery

logger = logging.getLogger(__name__)

# The Web API's maximum page size, which its listings use.
PAGE_SIZE = 100

Children = List[Dict[str, Any]]


def _item_type(child: Dict[str, Any]) -> Optional[str]:
    item_type = child.get("data", child).get("itemType")
    return item_type if isinstance(item_type, str) else None


def _of_type(children: Children, item_type: Optional[str]) -> Children:
    if item_type is None:
        return list(children)
    return [c for c in children if _item_type(c) == item_type]


def _count(gateway: ZoteroGateway, item_type: Optional[str]) -> Optional[int]:
    # Looked up on the class, so a test double without the method (or a
    # MagicMock, which would invent one) takes the per-parent path.
    count = getattr(type(gateway), "count_search_results", None)
    if count is None:
        return None
    total = count(gateway, ZoteroQuery(item_type=item_type))
    return total if isinstance(total, int) else None


def should_scan(gateway: ZoteroGateway, parents: int, item_type: Optional[str]) -> bool:
    """True when one scan of `item_type` needs fewer requests than one
    children request per parent."""
    total = _count(gateway, item_type)
    return total is not None and parents > math.ceil(total / PAGE_SIZE)


def children_by_parent(
    gateway: ZoteroGateway,
    parent_keys: Iterable[str],
    item_type: Optional[str] = None,
) -> Dict[str, Children]:
    """
    Every parent key mapped to its children (raw Web API dicts), optionally
    only those of `item_type` ("note", "attachment"). Parents without
    children map to an empty list. Errors propagate.
    """
    keys = list(dict.fromkeys(parent_keys))
    if not keys:
        return {}

    batch = getattr(type(gateway), "get_children_by_parent", None)
    if batch is not None:
        grouped: Dict[str, Children] = batch(gateway, keys)
        return {key: _of_type(grouped.get(key, []), item_type) for key in keys}

    if should_scan(gateway, len(keys), item_type):
        wanted = set(keys)
        by_parent: Dict[str, Children] = {key: [] for key in keys}
        for item in gateway.search_items(ZoteroQuery(item_type=item_type)):
            if item.parent_item in wanted:
                by_parent[item.parent_item].append(item.raw_data)
        logger.debug("children of %d parents from one %s scan", len(keys), item_type or "item")
        return by_parent

    return {key: _of_type(gateway.get_item_children(key), item_type) for key in keys}
