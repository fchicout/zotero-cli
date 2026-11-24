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
import os
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from zotero_cli.core.zotero_item import ZoteroItem

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

    def is_trashed(self, key: str) -> bool:
        return self._in_trash(self.items[key])

    def live_items(self) -> List[Dict[str, Any]]:
        """What `/items` lists: everything not in the trash itself. As in the real API that
        includes the children of a trashed parent (probe of 2026-11-24)."""
        return [r for r in self.items.values() if not r["data"].get("deleted")]

    def trashed_items(self) -> List[Dict[str, Any]]:
        """What `/items/trash` lists: the items with their own `deleted` flag, not the
        children of a trashed parent."""
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


# --- the library under test ------------------------------------------------------------------

USER = ("user", "42")
GROUP = ("group", "777")
PDF = b"%PDF-1.7 " + bytes(range(256)) * 20
SNAPSHOT = b"<html><body>saved page</body></html>"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

# Everything Zotero shows (not in the trash), by role.
LIVE_KEYS = {
    "COLLECTION_TREE": ["COLA0001", "COLA1001", "COLA1A01", "COLB0001"],
    "TOP": ["JRN00001", "BOOK0001", "NOTE0001", "STND0001", "UNFI0001", "UNIC0001"],
    "CHILDREN": [
        "PDF00001",
        "ANN00001",
        "ANN00002",
        "SNP00001",
        "LNK00001",
        "LFL00001",
        "NOT00001",
        "EMB00001",
        "BK1PDF01",
        "UNFN0001",
        "UNIC0002",
    ],
}
ALL_LIVE = LIVE_KEYS["TOP"] + LIVE_KEYS["CHILDREN"]


def populate(lib: FakeLibrary) -> FakeLibrary:
    """A library with every shape of item Zotero has: nested collections, an item in two
    collections, related items, PDFs with annotations, snapshots, links, linked files, notes with
    embedded images, stand-alone notes and files, unfiled items, Unicode, and trash."""
    lib.add_collection("COLA0001", "Reviews")
    lib.add_collection("COLA1001", "2025", parent="COLA0001")
    lib.add_collection("COLA1A01", "Drafts", parent="COLA1001")
    lib.add_collection("COLB0001", "Reading list")

    lib.add_item(
        "JRN00001",
        "journalArticle",
        collections=["COLA0001", "COLB0001"],
        title="A study of backups",
        creators=[
            {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"},
            {"creatorType": "editor", "name": "The Committee"},
        ],
        abstractNote="Everything must be kept.",
        DOI="10.1000/backup.1",
        date="2025-06-01",
        extra="arXiv: 2501.00001",
        tags=[{"tag": "to-read", "type": 0}, {"tag": "auto", "type": 1}],
        relations={"dc:relation": [lib.item_uri("BOOK0001")]},
    )
    lib.add_item(
        "PDF00001",
        "attachment",
        parent="JRN00001",
        linkMode="imported_file",
        filename="study.pdf",
        title="Full text",
        contentType="application/pdf",
        file=PDF,
    )
    lib.add_item(
        "ANN00001", "annotation", parent="PDF00001", annotationType="highlight", annotationText="x"
    )
    lib.add_item(
        "ANN00002", "annotation", parent="PDF00001", annotationType="note", annotationComment="y"
    )
    lib.add_item(
        "SNP00001",
        "attachment",
        parent="JRN00001",
        linkMode="imported_url",
        filename="snapshot.html",
        url="https://example.org/paper",
        contentType="text/html",
        file=SNAPSHOT,
    )
    lib.add_item(
        "LNK00001",
        "attachment",
        parent="JRN00001",
        linkMode="linked_url",
        title="Publisher page",
        url="https://example.org/paper",
    )
    lib.add_item(
        "LFL00001",
        "attachment",
        parent="JRN00001",
        linkMode="linked_file",
        filename="local.pdf",
        path="/home/someone/papers/local.pdf",
    )
    lib.add_item(
        "NOT00001",
        "note",
        parent="JRN00001",
        note='<p>Read this</p><img data-attachment-key="EMB00001"/>',
        tags=[{"tag": "note-tag"}],
    )
    lib.add_item(
        "EMB00001",
        "attachment",
        parent="NOT00001",
        linkMode="embedded_image",
        contentType="image/png",
        file=PNG,
    )

    lib.add_item(
        "BOOK0001",
        "book",
        collections=["COLA1A01"],
        title="The book",
        relations={"dc:relation": [lib.item_uri("JRN00001")]},
    )
    lib.add_item(
        "BK1PDF01",
        "attachment",
        parent="BOOK0001",
        linkMode="imported_file",
        filename="book.pdf",
        contentType="application/pdf",
        file=PDF + b"book",
    )
    lib.add_item("NOTE0001", "note", collections=["COLA1001"], note="<p>stand-alone note</p>")
    lib.add_item(
        "STND0001",
        "attachment",
        collections=["COLA0001"],
        linkMode="imported_file",
        filename="loose.pdf",
        contentType="application/pdf",
        file=PDF + b"loose",
    )
    lib.add_item("UNFI0001", "thesis", title="Unfiled thesis")
    lib.add_item("UNFN0001", "note", parent="UNFI0001", note="<p>child of an unfiled item</p>")
    lib.add_item("UNIC0001", "book", collections=["COLB0001"], title="Ação & relatório – 研究")
    lib.add_item(
        "UNIC0002",
        "attachment",
        parent="UNIC0001",
        linkMode="imported_file",
        filename="relatório ação.pdf",
        contentType="application/pdf",
        file=PDF + b"unicode",
    )

    lib.add_item("TRSH0001", "book", collections=["COLA0001"], title="Deleted book", deleted=True)
    lib.add_item("TRSHN001", "note", parent="TRSH0001", note="<p>in the trash</p>")
    lib.searches["SRCH0001"] = {
        "key": "SRCH0001",
        "version": 5,
        "data": {"key": "SRCH0001", "name": "Unread", "conditions": [{"condition": "tag"}]},
    }
    return lib


class FakeTarget:
    """The library a restore writes into: the repository calls `RestoreService` makes,
    answered the way the Web API answers them (new keys, a parent must exist, an
    annotation needs an attachment as its parent, `parentCollection` is False for a
    root). It deliberately keeps what the *current* client sends, so a gap in the
    restore shows up as a difference, not as a fake that is kinder than the API."""

    NOW = "2026-11-24T12:00:00Z"

    def __init__(self, library_id: str = "8888", library_type: str = "user") -> None:
        self.lib = FakeLibrary(library_type, library_id, "Restore target")
        self._count = 0

    def _new_key(self) -> str:
        self._count += 1
        return f"NEW{self._count:05d}"

    # --- reads --------------------------------------------------------------------------

    def get_all_items(self) -> Iterator[ZoteroItem]:
        for raw in self.lib.live_items():
            yield ZoteroItem.from_raw_zotero_item(copy.deepcopy(raw))

    def get_trash_items(self) -> Iterator[ZoteroItem]:
        for raw in self.lib.trashed_items():
            yield ZoteroItem.from_raw_zotero_item(copy.deepcopy(raw))

    def get_all_collections(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(list(self.lib.collections.values()))

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.lib.children_of(item_key))

    # --- writes -------------------------------------------------------------------------

    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        if item_key not in self.lib.items:
            return False
        self.lib.items[item_key]["data"].update(copy.deepcopy(item_data))
        return True

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        if parent_key is not None and parent_key not in self.lib.collections:
            return None
        return self.lib.add_collection(self._new_key(), name, parent=parent_key)

    def create_generic_item(self, data: Dict[str, Any]) -> Optional[str]:
        parent = data.get("parentItem")
        if parent is not None and parent not in self.lib.items:
            return None  # 409 "Parent item ... not found"
        if data["itemType"] == "annotation" and (
            parent is None or self.lib.items[parent]["data"]["itemType"] != "attachment"
        ):
            return None
        if any(key not in self.lib.collections for key in data.get("collections", [])):
            return None
        if self.lib.library_type == "group" and data.get("linkMode") == "linked_file":
            return None  # 400 "Linked files can only be added to user libraries"
        fields = {
            k: v
            for k, v in data.items()
            if k not in ("key", "version", "itemType", "parentItem", "collections", "deleted")
        }
        fields.setdefault("dateAdded", self.NOW)
        fields.setdefault("dateModified", self.NOW)
        return self.lib.add_item(
            self._new_key(),
            data["itemType"],
            parent=parent,
            collections=data.get("collections"),
            deleted=bool(data.get("deleted")),
            **fields,
        )

    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        if parent_item_key not in self.lib.items:
            return False
        self.lib.add_item(
            self._new_key(),
            "note",
            parent=parent_item_key,
            note=note_content,
            dateAdded=self.NOW,
            dateModified=self.NOW,
        )
        return True

    def upload_attachment(
        self,
        parent_item_key: Optional[str],
        file_path: str,
        mime_type: str = "application/pdf",
        item_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return (
            self.upload_attachment_item(parent_item_key, file_path, mime_type, item_data)
            is not None
        )

    def upload_attachment_item(
        self,
        parent_item_key: Optional[str],
        file_path: str,
        mime_type: str = "application/pdf",
        item_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if parent_item_key is not None and parent_item_key not in self.lib.items:
            return None
        collections = (item_data or {}).get("collections") or None
        if any(key not in self.lib.collections for key in collections or []):
            return None
        name = os.path.basename(file_path)  # what the client names the item after, by default
        with open(file_path, "rb") as stored:
            content = stored.read()
        fields: Dict[str, Any] = {
            "linkMode": "imported_file",
            "filename": name,
            "title": name,
            "contentType": mime_type,
            "dateAdded": self.NOW,
            "dateModified": self.NOW,
        }
        fields.update(
            {
                k: v
                for k, v in (item_data or {}).items()
                if k not in ("collections", "deleted", "parentItem")
            }
        )
        return self.lib.add_item(
            self._new_key(),
            "attachment",
            parent=parent_item_key,
            collections=collections,
            deleted=bool((item_data or {}).get("deleted")),
            file=content,
            **fields,
        )
