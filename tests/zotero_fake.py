"""An in-memory Zotero Web API (v3) for backup tests.

It stands in for `requests.Session` under the real `ZoteroHttpClient`, so the real
`ZoteroAPIClient`, gateway factory, `BackupService` and CLI handlers all run
unchanged against realistic JSON. Endpoints follow the documented v3 behaviour:

- `/items` lists every item of the library, children and annotations included, but not
  what is in the trash; `/items/top` lists the top-level ones; `/items/trash` the trash.
- `/collections/<key>/items` lists the items filed directly in that collection (not in
  its sub-collections) together with their children; `.../items/top` only the former.
- Listings page with `limit`/`start` and report `Total-Results`.
- `/items/<key>/file` serves a stored file; a linked file or a link has none (404).

Libraries are registered under ("user"|"group", id); a request for a library nobody
registered raises, so a backup that targets the wrong library fails loudly.
"""

import copy
import hashlib
import json
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlparse

import requests

FILE_ITEM_LINK_MODES = ("imported_file", "imported_url", "embedded_image")


def _response(status: int, body: Any, url: str, headers: Optional[Dict[str, str]] = None):
    response = requests.Response()
    response.status_code = status
    response.url = url
    payload = body if isinstance(body, bytes) else json.dumps(body).encode()
    response._content = payload
    response._content_consumed = True  # type: ignore[attr-defined]
    response.headers.update(headers or {})
    response.headers.setdefault("Content-Length", str(len(payload)))
    return response


class FakeLibrary:
    """One Zotero library (a user's or a group's) and its stored files."""

    def __init__(self, library_type: str, library_id: str, name: str = "Library"):
        self.library_type = library_type
        self.library_id = library_id
        self.name = name
        self.version = 1
        self.items: Dict[str, Dict[str, Any]] = {}
        self.collections: Dict[str, Dict[str, Any]] = {}
        self.searches: Dict[str, Dict[str, Any]] = {}
        self.files: Dict[str, bytes] = {}
        # Keys whose file download fails with a server error (outage on one file).
        self.broken_files: set = set()
        # Endpoints (path suffix after the library prefix) that answer 500.
        self.failing: set = set()
        self.requests: List[str] = []
        # A library the API key has no access to: every request is answered 403.
        self.forbidden = False
        # Whether /items/trash also lists the children of a trashed parent (the real API may
        # not): a backup must not depend on it.
        self.trash_lists_children = True

    # --- building ---------------------------------------------------------

    def _library_stub(self) -> Dict[str, Any]:
        return {"type": self.library_type, "id": int(self.library_id), "name": self.name}

    def _tick(self) -> int:
        self.version += 1
        return self.version

    def add_collection(self, key: str, name: str, parent: Optional[str] = None) -> str:
        version = self._tick()
        self.collections[key] = {
            "key": key,
            "version": version,
            "library": self._library_stub(),
            "data": {
                "key": key,
                "version": version,
                "name": name,
                "parentCollection": parent or False,
                "relations": {},
            },
            "meta": {"numCollections": 0, "numItems": 0},
        }
        return key

    def add_item(
        self,
        key: str,
        item_type: str,
        parent: Optional[str] = None,
        collections: Optional[List[str]] = None,
        file: Optional[bytes] = None,
        deleted: bool = False,
        **fields: Any,
    ) -> str:
        version = self._tick()
        data: Dict[str, Any] = {
            "key": key,
            "version": version,
            "itemType": item_type,
            "tags": [],
            "relations": {},
            "collections": list(collections or []),
            "dateAdded": "2026-01-01T10:00:00Z",
            "dateModified": "2026-01-02T10:00:00Z",
        }
        if parent:
            data["parentItem"] = parent
        if deleted:
            data["deleted"] = 1
        data.update(fields)
        self.items[key] = {
            "key": key,
            "version": version,
            "library": self._library_stub(),
            "links": {"self": {"href": f"https://api.zotero.org/items/{key}"}},
            "meta": {"numChildren": 0},
            "data": data,
        }
        if file is not None:
            self.files[key] = file
            data["md5"] = hashlib.md5(file).hexdigest()  # noqa: S324 - Zotero's own field
        return key

    def item_uri(self, key: str) -> str:
        prefix = "users" if self.library_type == "user" else "groups"
        return f"http://zotero.org/{prefix}/{self.library_id}/items/{key}"

    # --- queries ----------------------------------------------------------

    def _in_trash(self, raw: Dict[str, Any]) -> bool:
        data = raw["data"]
        if data.get("deleted"):
            return True
        parent = data.get("parentItem")
        return bool(parent and parent in self.items and self._in_trash(self.items[parent]))

    def live_items(self) -> List[Dict[str, Any]]:
        return [r for r in self.items.values() if not self._in_trash(r)]

    def trashed_items(self) -> List[Dict[str, Any]]:
        if self.trash_lists_children:
            return [r for r in self.items.values() if self._in_trash(r)]
        return [r for r in self.items.values() if r["data"].get("deleted")]

    def children_of(self, key: str) -> List[Dict[str, Any]]:
        """A parent's children by key, whether the parent is in the trash or not; only a
        child that is itself in the trash is left out."""
        return [
            r
            for r in self.items.values()
            if r["data"].get("parentItem") == key and not r["data"].get("deleted")
        ]

    def items_in_collection(self, key: str) -> List[Dict[str, Any]]:
        direct = [r for r in self.live_items() if key in r["data"].get("collections", [])]
        found = list(direct)
        queue = [r["key"] for r in direct]
        while queue:  # children, then annotations (children of attachments)
            for child in self.children_of(queue.pop(0)):
                found.append(child)
                queue.append(child["key"])
        return found

    def raw_copy(self, key: str) -> Dict[str, Any]:
        return copy.deepcopy(self.items[key])


class FakeZoteroServer:
    """Every registered library, answering as `api.zotero.org` would."""

    def __init__(self) -> None:
        self.libraries: Dict[Tuple[str, str], FakeLibrary] = {}

    def register(self, library: FakeLibrary) -> FakeLibrary:
        self.libraries[(library.library_type, library.library_id)] = library
        return library

    def session(self) -> "FakeSession":
        return FakeSession(self)


class FakeSession:
    """The part of `requests.Session` the Zotero client uses."""

    def __init__(self, server: FakeZoteroServer) -> None:
        self.server = server
        self.headers: Dict[str, str] = {}

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, **_: Any):
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        scope = {"users": "user", "groups": "group"}.get(parts[0])
        if scope is None or len(parts) < 3:
            raise AssertionError(f"unexpected Zotero URL {url}")
        library = self.server.libraries.get((scope, parts[1]))
        if library is None:
            raise AssertionError(f"request for an unregistered library: {url}")
        endpoint = "/".join(parts[2:])
        library.requests.append(endpoint)
        if library.forbidden:
            return _response(403, {"error": "forbidden"}, url)
        if endpoint in library.failing:
            return _response(500, {"error": "boom"}, url)
        return self._route(library, endpoint, dict(params or {}), url)

    # --- routing ----------------------------------------------------------

    def _route(self, lib: FakeLibrary, endpoint: str, params: Dict[str, Any], url: str):
        parts = endpoint.split("/")
        head = parts[0]
        if endpoint == "items":
            return self._page(self._filter_type(lib.live_items(), params), params, url, lib)
        if endpoint == "items/top":
            top = [r for r in lib.live_items() if "parentItem" not in r["data"]]
            return self._page(self._filter_type(top, params), params, url, lib)
        if endpoint == "items/trash":
            return self._page(lib.trashed_items(), params, url, lib)
        if head == "items" and len(parts) >= 2:
            return self._one_item(lib, parts, params, url)
        if endpoint == "collections":
            return self._page(list(lib.collections.values()), params, url, lib)
        if head == "collections" and len(parts) == 2:
            found = lib.collections.get(parts[1])
            if found is None:
                return _response(404, {}, url)
            return _response(200, found, url, {"Last-Modified-Version": str(lib.version)})
        if head == "collections" and len(parts) >= 3 and parts[2] == "items":
            if parts[1] not in lib.collections:
                return _response(404, {}, url)
            members = lib.items_in_collection(parts[1])
            if parts[3:] == ["top"]:
                members = [r for r in members if "parentItem" not in r["data"]]
            return self._page(self._filter_type(members, params), params, url, lib)
        if endpoint == "searches":
            return self._page(list(lib.searches.values()), params, url, lib)
        raise AssertionError(f"endpoint not emulated: {endpoint}")

    def _one_item(self, lib: FakeLibrary, parts: List[str], params: Dict[str, Any], url: str):
        raw = lib.items.get(parts[1])
        if raw is None:
            return _response(404, {}, url)
        if len(parts) == 2:
            return _response(200, raw, url, {"Last-Modified-Version": str(lib.version)})
        if parts[2] == "children":
            return self._page(lib.children_of(parts[1]), params, url, lib)
        if parts[2] == "file":
            if parts[1] in lib.broken_files:
                return _response(500, {"error": "storage down"}, url)
            if parts[1] not in lib.files:
                return _response(404, {}, url)  # a link or a linked file: nothing stored
            return _response(200, lib.files[parts[1]], url)
        raise AssertionError(f"item endpoint not emulated: {'/'.join(parts)}")

    @staticmethod
    def _filter_type(rows: List[Dict[str, Any]], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        wanted = params.get("itemType")
        if not wanted:
            return rows
        return [r for r in rows if r["data"].get("itemType") == wanted]

    @staticmethod
    def _page(rows: List[Dict[str, Any]], params: Dict[str, Any], url: str, lib: FakeLibrary):
        start = int(params.get("start", 0))
        limit = int(params.get("limit", 25))
        chunk = rows[start : start + limit]
        headers = {"Total-Results": str(len(rows)), "Last-Modified-Version": str(lib.version)}
        return _response(200, copy.deepcopy(chunk), url, headers)


def iter_keys(rows: List[Dict[str, Any]]) -> Iterator[str]:
    for row in rows:
        yield row["key"]
