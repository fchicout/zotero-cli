import hashlib
import logging
import os
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar, cast

import requests

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import KeyIdentity, ResearchPaper, ZoteroQuery
from zotero_cli.core.utils.normalization import normalize_doi
from zotero_cli.core.utils.url_safety import (
    ResponseTooLargeError,
    UnsafeURLError,
    iter_capped_content,
    safe_get,
)
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.http_client import ZoteroHttpClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ZoteroAPIClient(ZoteroGateway):
    """
    Implementation of ZoteroGateway using ZoteroHttpClient.
    Focuses on Domain Object mapping (JSON -> ZoteroItem) and Business Logic.
    """

    def __init__(self, api_key: str, library_id: str, library_type: str = "group"):
        self.http = ZoteroHttpClient(api_key, library_id, library_type)

    @staticmethod
    def resolve_key_identity(api_key: str) -> KeyIdentity:
        """
        Resolves the userID/username/access scopes for a bare Zotero API
        key, with no library_id required (Issue #178) - this is how a
        caller discovers their personal library_id (== userID) in the
        first place, e.g. an account-setup flow that hasn't asked for a
        library/group yet. A `@staticmethod` deliberately, since the
        instance constructor above requires the library_id this method
        exists to produce.
        """
        data = ZoteroHttpClient.resolve_key_identity(api_key)
        return KeyIdentity(
            user_id=data["userID"],
            username=data.get("username", ""),
            access=data.get("access", {}),
        )

    def _safe_execute(self, operation: str, default_val: T, func: Callable[[], T]) -> T:
        try:
            return func()
        except Exception:
            logger.exception(f"ZoteroAPIClient: Error {operation}")
            return default_val

    def _parse_write_response(self, response: requests.Response) -> Optional[str]:
        data = cast(Dict[str, Any], response.json())
        if "successful" in data and data["successful"]:
            first_index = next(iter(data["successful"].keys()))
            return str(data["successful"][first_index]["key"])
        if "failed" in data and data["failed"]:
            logger.warning(f"ZoteroAPIClient: Write failed details: {data['failed']}")
        return None

    def _paginate_items(self, endpoint: str, params: Optional[Dict] = None) -> Iterator[ZoteroItem]:
        limit = 100
        start = 0
        if params is None:
            params = {}
        params["limit"] = limit

        while True:
            try:
                params["start"] = start
                response = self.http.get(endpoint, params=params)
                items = cast(List[Dict[str, Any]], response.json())
                if not items:
                    break
                for item in items:
                    yield ZoteroItem.from_raw_zotero_item(item)
                start += len(items)
                if len(items) < limit:
                    break
            except Exception:
                logger.exception(f"ZoteroAPIClient: Error fetching items from {endpoint}")
                break

    # --- Read Operations ---

    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        return self._safe_execute(
            "fetching user groups",
            [],
            lambda: cast(
                List[Dict[str, Any]],
                self.http.get(f"users/{user_id}/groups", use_prefix=False).json(),
            ),
        )

    def get_all_collections(self) -> List[Dict[str, Any]]:
        return self._safe_execute(
            "fetching collections",
            [],
            lambda: cast(
                List[Dict[str, Any]], self.http.get("collections", params={"limit": 100}).json()
            ),
        )

    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        return self._safe_execute(
            f"fetching collection {collection_key}",
            None,
            lambda: cast(
                Optional[Dict[str, Any]], self.http.get(f"collections/{collection_key}").json()
            ),
        )

    def get_tags(self) -> List[str]:
        def _fetch_tags() -> List[str]:
            response = self.http.get("tags", params={"limit": 100})
            tags_data = cast(List[Dict[str, Any]], response.json())
            return [t["tag"] for t in tags_data]

        return self._safe_execute("fetching tags", [], _fetch_tags)

    def get_tags_for_item(self, item_key: str) -> List[str]:
        return self._safe_execute(
            f"fetching tags for item {item_key}",
            [],
            lambda: [
                t["tag"]
                for t in cast(List[Dict[str, Any]], self.http.get(f"items/{item_key}/tags").json())
            ],
        )

    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        return self._paginate_items("items", params=query.to_params())

    def verify_credentials(self) -> bool:
        """
        Verifies that the API key and Library ID are valid by making a lightweight request.
        """
        try:
            # We use items with limit 1 as a lightweight check
            self.http.get("items", params={"limit": 1})
            return True
        except Exception:
            return False

    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        return self.search_items(ZoteroQuery(tag=tag))

    def get_items_by_doi(self, doi: str) -> Iterator[ZoteroItem]:
        """
        Zotero's `q`/`qmode` search does not index the structured DOI
        field under either `qmode` value (Issue #205, reopened) -
        confirmed directly against the live Web API: `q=<doi>` with both
        `qmode=titleCreatorYear` and `qmode=everything` returns zero
        results for a DOI that genuinely exists on an item in the
        library. A client-side scan is the only approach that actually
        works: paginate every item and filter locally with
        `normalize_doi()`, so bare/URL-form/case differences in how a
        DOI was stored don't matter either. This is a full library scan
        per call - acceptably slow for a duplicate-detection check
        that's normally called once per candidate during a snowball
        import, not a hot path.
        """
        target = normalize_doi(doi)
        if not target:
            return
        for item in self.get_all_items():
            if item.doi and normalize_doi(item.doi) == target:
                yield item

    def get_all_items(self) -> Iterator[ZoteroItem]:
        return self.search_items(ZoteroQuery())

    def get_trash_items(self) -> Iterator[ZoteroItem]:
        return self._paginate_items("items/trash")

    def get_orphan_items(self, top_only: bool = False) -> Iterator[ZoteroItem]:
        endpoint = "items/top" if top_only else "items"
        return self._paginate_items(endpoint, params={"collection": "none"})

    def get_items_in_collection(
        self, collection_id: str, top_only: bool = False
    ) -> Iterator[ZoteroItem]:
        endpoint = f"collections/{collection_id}/items"
        if top_only:
            endpoint += "/top"
        return self._paginate_items(endpoint)

    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        def _fetch() -> ZoteroItem:
            raw = self.http.get(f"items/{item_key}").json()
            if not isinstance(raw, dict):
                # A malformed/non-existent key (e.g. a bare DOI passed where a
                # short alphanumeric Zotero item key is expected) can route to
                # an endpoint that returns a list rather than a 404 - fail with
                # a clear message instead of an opaque AttributeError from
                # ZoteroItem.from_raw_zotero_item (Issue #207).
                raise ValueError(
                    f"'{item_key}' is not a valid Zotero item key "
                    f"(expected an item object, got {type(raw).__name__})"
                )
            return ZoteroItem.from_raw_zotero_item(cast(Dict[str, Any], raw))

        return self._safe_execute(f"fetching item {item_key}", None, _fetch)

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        return self._safe_execute(
            f"fetching children for {item_key}",
            [],
            lambda: cast(List[Dict[str, Any]], self.http.get(f"items/{item_key}/children").json()),
        )

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        cols = self.get_all_collections()
        for c in cols:
            if c.get("data", {}).get("name") == name:
                return str(c["key"])
        return None

    # --- Write Operations ---

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        payload = {"name": name}
        if parent_key:
            payload["parentCollection"] = parent_key

        try:
            response = self.http.post("collections", json_data=[payload])
            return self._parse_write_response(response)
        except Exception:
            logger.exception("ZoteroAPIClient: Error creating collection")
            return None

    def delete_collection(self, collection_key: str, version: int) -> bool:
        try:
            response = self.http.delete(f"collections/{collection_key}", version_check=True)
            if response.status_code == 412:
                self.http.delete(f"collections/{collection_key}", version_check=True)
            return True
        except Exception:
            logger.exception(f"ZoteroAPIClient: Error deleting collection {collection_key}")
            return False

    def rename_collection(self, collection_key: str, version: int, name: str) -> bool:
        try:
            self.http.patch(
                f"collections/{collection_key}", json_data={"name": name}, version_check=True
            )
            return True
        except Exception:
            logger.exception(f"ZoteroAPIClient: Error renaming collection {collection_key}")
            return False

    def add_tags(self, item_key: str, tags: List[str]) -> bool:
        if not tags:
            return True
        item = self.get_item(item_key)
        if not item:
            return False

        current_tags = [t["tag"] for t in item.raw_data.get("data", {}).get("tags", [])]
        updated_tags = set(current_tags) | set(tags)
        tag_payload = [{"tag": t} for t in updated_tags]

        return self.update_item(item_key, item.version, {"tags": tag_payload})

    def delete_tags(self, tags: List[str], version: int) -> bool:
        if not tags:
            return True
        # Chunking: Zotero supports up to 50 tags per request
        chunk_size = 50
        success = True
        for i in range(0, len(tags), chunk_size):
            chunk = tags[i : i + chunk_size]
            tags_query = " || ".join(chunk)
            try:
                self.http.delete("tags", params={"tag": tags_query}, version_check=True)
            except Exception:
                logger.exception("ZoteroAPIClient: Error deleting tags chunk")
                success = False
        return success

    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        creators = []
        for author in paper.authors:
            parts = author.rsplit(" ", 1)
            if len(parts) == 2:
                creators.append(
                    {"creatorType": "author", "firstName": parts[0], "lastName": parts[1]}
                )
            else:
                creators.append({"creatorType": "author", "name": author})

        # Detect thesis items (from BDTD or other academic repositories)
        is_thesis = self._is_thesis_paper(paper)

        if is_thesis:
            item_payload = self._build_thesis_payload(paper, creators, collection_id)
        else:
            item_payload = {
                "itemType": "journalArticle",
                "title": paper.title,
                "abstractNote": paper.abstract,
                "creators": creators,
                "collections": [collection_id],
            }

            if paper.url:
                item_payload["url"] = paper.url
            elif paper.arxiv_id:
                item_payload["url"] = f"https://arxiv.org/abs/{paper.arxiv_id}"

            if paper.arxiv_id:
                item_payload["libraryCatalog"] = "arXiv"
                extra_lines = [f"arXiv: {paper.arxiv_id}"]
                if paper.extra:
                    extra_lines.append(paper.extra)
                item_payload["extra"] = "\n".join(extra_lines)
            elif paper.extra:
                item_payload["extra"] = paper.extra

            if paper.doi:
                item_payload["DOI"] = paper.doi
            if paper.publication:
                item_payload["publicationTitle"] = paper.publication
            if paper.year:
                item_payload["date"] = paper.year

        try:
            response = self.http.post("items", json_data=[item_payload])
            item_key = self._parse_write_response(response)

            # Download and attach PDF for thesis items if available
            if item_key and is_thesis and paper.pdf_url:
                dest = None
                try:
                    import tempfile
                    from pathlib import Path

                    headers = {
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0"
                    }
                    # paper.pdf_url originates from a third-party metadata
                    # provider (untrusted input) - fetched via safe_get,
                    # which validates the URL and every redirect hop
                    # against a public-address allowlist before fetching
                    # (Issue #235), instead of trusting requests' default
                    # redirect-following.
                    resp = safe_get(paper.pdf_url, stream=True, timeout=30, headers=headers)

                    if resp.status_code == 200:
                        # Non-predictable temp path (Issue #240) - a
                        # manually joined
                        # tempfile.gettempdir()/f"thesis_{item_key}.pdf"
                        # path is fully deterministic, letting a local
                        # attacker on a shared host pre-plant a symlink
                        # there. tempfile.mkstemp creates the file itself
                        # (O_CREAT|O_EXCL, mode 0600), so there's nothing
                        # for an attacker to have pre-planted.
                        fd, dest_str = tempfile.mkstemp(prefix="thesis_", suffix=".pdf")
                        dest = Path(dest_str)
                        is_pdf = True
                        first_chunk = True
                        with os.fdopen(fd, "wb") as f:
                            # iter_capped_content enforces a hard size cap
                            # (Issue #239) - a malicious/compromised
                            # metadata source could otherwise exhaust disk
                            # via an arbitrarily large or slow-drip body.
                            for chunk in iter_capped_content(resp, chunk_size=8192):
                                if first_chunk:
                                    # Verify the %PDF magic bytes before
                                    # ever uploading this into the library
                                    # (Issue #235).
                                    is_pdf = chunk.startswith(b"%PDF")
                                    first_chunk = False
                                f.write(chunk)

                        if is_pdf:
                            self.upload_attachment(item_key, str(dest))
                        else:
                            logger.warning(
                                f"ZoteroAPIClient: {paper.pdf_url!r} did not return a valid "
                                "PDF signature; skipping upload."
                            )
                        dest.unlink(missing_ok=True)
                except UnsafeURLError as attach_err:
                    logger.warning(
                        f"ZoteroAPIClient: refusing unsafe PDF URL for thesis {item_key}: {attach_err}"
                    )
                except ResponseTooLargeError as attach_err:
                    logger.warning(
                        f"ZoteroAPIClient: PDF response too large for thesis {item_key}: {attach_err}"
                    )
                    if dest is not None:
                        dest.unlink(missing_ok=True)
                except Exception:
                    logger.exception(
                        f"ZoteroAPIClient: Failed to download and attach PDF for thesis {item_key}"
                    )
                    if dest is not None:
                        dest.unlink(missing_ok=True)

            return bool(item_key)
        except Exception:
            logger.exception("ZoteroAPIClient: Error creating item")
            return False

    def _is_thesis_paper(self, paper: ResearchPaper) -> bool:
        """Detects if a ResearchPaper represents a thesis/dissertation."""
        # Check extra field for degree level marker
        if paper.extra and "Degree Level:" in paper.extra:
            return True
        # Check URL for academic repository patterns
        if paper.url:
            lower_url = paper.url.lower()
            repo_markers = ["bdtd.ibict.br", "/tede/", "/jspui/handle/tede/"]
            if any(marker in lower_url for marker in repo_markers):
                return True
        return False

    def _build_thesis_payload(
        self, paper: ResearchPaper, creators: list, collection_id: str
    ) -> dict:
        """Builds a Zotero 'thesis' item payload from a ResearchPaper."""
        # Extract degree level and clean extra
        degree_level = ""
        extra_lines_clean = []
        if paper.extra:
            for line in paper.extra.split("\n"):
                if line.startswith("Degree Level:"):
                    degree_level = line.split(":", 1)[1].strip()
                else:
                    extra_lines_clean.append(line)

        # Map common BDTD format values to human-readable thesis types
        thesis_type_map = {
            "masterThesis": "Master's Thesis",
            "doctoralDissertation": "Doctoral Dissertation",
            "masterthesis": "Master's Thesis",
            "doctoraldissertation": "Doctoral Dissertation",
        }
        thesis_type = thesis_type_map.get(degree_level, degree_level)

        item_payload = {
            "itemType": "thesis",
            "title": paper.title,
            "abstractNote": paper.abstract,
            "creators": creators,
            "collections": [collection_id],
            "thesisType": thesis_type,
        }

        # Map institution -> university
        if paper.publication:
            item_payload["university"] = paper.publication

        if paper.url:
            item_payload["url"] = paper.url
        if paper.doi:
            item_payload["DOI"] = paper.doi
        if paper.year:
            item_payload["date"] = paper.year

        extra_clean = "\n".join(extra_lines_clean).strip()
        if extra_clean:
            item_payload["extra"] = extra_clean

        return item_payload

    def get_item_template(self, item_type: str) -> Dict[str, Any]:
        return self._safe_execute(
            f"fetching template for {item_type}",
            {},
            lambda: cast(
                Dict[str, Any],
                self.http.get("items/new", params={"itemType": item_type}, use_prefix=False).json(),
            ),
        )

    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        try:
            response = self.http.post("items", json_data=[item_data])
            return self._parse_write_response(response)
        except Exception:
            logger.exception("ZoteroAPIClient: Error creating generic item")
            return None

    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        try:
            self.http.patch(f"items/{item_key}", json_data=item_data, version_check=True)
            return True
        except Exception:
            logger.exception(f"ZoteroAPIClient: Error updating item {item_key}")
            return False

    def update_items(self, items_data: List[Dict[str, Any]]) -> bool:
        if not items_data:
            return True
        try:
            # Zotero API supports up to 50 items in a single multi-item request
            chunk_size = 50
            all_success = True
            for i in range(0, len(items_data), chunk_size):
                chunk = items_data[i : i + chunk_size]
                response = self.http.post("items", json_data=chunk, version_check=False)
                # Parse response to check for individual failures if needed
                # For now, response.raise_for_status() in http.post handles errors
                if response.status_code not in [200, 204, 207]:
                    all_success = False
            return all_success
        except Exception:
            logger.exception("ZoteroAPIClient: Error updating bulk items")
            return False

    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        payload = [{"itemType": "note", "parentItem": parent_item_key, "note": note_content}]
        try:
            response = self.http.post("items", json_data=payload)
            return bool(self._parse_write_response(response))
        except Exception:
            logger.exception(f"ZoteroAPIClient: Error creating note for {parent_item_key}")
            return False

    def update_note(
        self, note_key: str, version: int, note_content: str, parent_item_key: Optional[str] = None
    ) -> bool:
        payload = {"note": note_content, "version": version}
        if parent_item_key:
            payload["parentItem"] = parent_item_key
        try:
            response = self.http.patch(f"items/{note_key}", json_data=payload, version_check=False)
            if response.status_code == 412:
                new_version = self.http.last_library_version
                payload["version"] = new_version
                self.http.patch(f"items/{note_key}", json_data=payload, version_check=False)
            return True
        except Exception:
            logger.exception(f"ZoteroAPIClient: Error updating note {note_key}")
            return False

    def delete_item(self, item_key: str, version: int) -> bool:
        try:
            response = self.http.delete(f"items/{item_key}", version_check=True)
            if response.status_code == 412:
                self.http.delete(f"items/{item_key}", version_check=True)
            return True
        except Exception:
            logger.exception(f"ZoteroAPIClient: Error deleting item {item_key}")
            return False

    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        return self.update_item(item_key, version, metadata)

    def upload_attachment(
        self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf"
    ) -> bool:
        attachment_key: Optional[str] = None
        try:
            filename = os.path.basename(file_path)
            filesize = os.path.getsize(file_path)
            mtime = int(os.path.getmtime(file_path) * 1000)

            md5_hash = hashlib.md5(usedforsecurity=False)
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            md5 = md5_hash.hexdigest()

            # 1. Create Attachment Item placeholder
            payload = [
                {
                    "itemType": "attachment",
                    "linkMode": "imported_file",
                    "parentItem": parent_item_key,
                    "title": filename,
                    "contentType": mime_type,
                }
            ]

            res = self.http.post("items", json_data=payload)
            attachment_key = self._parse_write_response(res)
            if not attachment_key:
                return False

            # 2. Get Upload Authorization
            auth_data = {"md5": md5, "filename": filename, "filesize": filesize, "mtime": mtime}
            # If-None-Match: * signals "no existing version of this attachment"
            # - true here since it was just created in step 1. Zotero 428s
            # this request if If-Unmodified-Since-Version is also sent
            # (Issue #191) - there's no prior version of *this* attachment to
            # be "unmodified since".
            headers = {
                "If-None-Match": "*",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            # Add params=1 as query param to get upload parameters
            auth_res = self.http.post_form(
                f"items/{attachment_key}/file?params=1", data=auth_data, headers=headers
            )
            auth_resp_data = auth_res.json()

            if auth_resp_data.get("exists") == 1:
                return True

            upload_url = auth_resp_data["url"]
            upload_params = auth_resp_data.get("params", {})
            upload_key = auth_resp_data.get("uploadKey")

            # 3. Perform the actual upload (typically to S3)
            with open(file_path, "rb") as f:
                self.http.upload_file(upload_url, data=upload_params, files={"file": f})

            # 4. Register the upload with Zotero - also needs If-None-Match: *
            # (Issue #191); Zotero rejects this call with 428 "If-Match/
            # If-None-Match header not provided" without it.
            reg_data = {"upload": upload_key}
            reg_headers = {"If-None-Match": "*", "Content-Type": "application/x-www-form-urlencoded"}
            self.http.post_form(f"items/{attachment_key}/file", data=reg_data, headers=reg_headers)

            return True

        except Exception:
            logger.exception("ZoteroAPIClient: Error uploading attachment")
            if attachment_key:
                # Steps 2-4 failed after step 1 already created the
                # attachment placeholder item - clean it up rather than
                # leaving an empty orphaned item behind (Issue #191).
                self.delete_item(attachment_key, 0)
            return False

    def download_attachment(self, item_key: str, save_path: str) -> bool:
        try:
            # Note: Zotero API redirects to Amazon S3 for file content
            response = self.http.get(f"items/{item_key}/file", stream=True)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception:
            logger.exception(f"ZoteroAPIClient: Error downloading attachment {item_key}")
            return False

    def update_attachment_link(self, item_key: str, version: int, new_path: str) -> bool:
        # Changes linkMode to 'linked_file' and sets the path
        payload = {"linkMode": "linked_file", "path": new_path, "version": version}
        return self.update_item(item_key, version, payload)
