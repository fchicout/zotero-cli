import hashlib
import os
from typing import Any, Callable, Dict, Iterator, List, Optional

import requests

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ResearchPaper, ZoteroQuery
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.http_client import ZoteroHttpClient


class ZoteroAPIClient(ZoteroGateway):
    """
    Implementation of ZoteroGateway using ZoteroHttpClient.
    Focuses on Domain Object mapping (JSON -> ZoteroItem) and Business Logic.
    """

    def __init__(self, api_key: str, library_id: str, library_type: str = 'group'):
        self.http = ZoteroHttpClient(api_key, library_id, library_type)

    def _safe_execute(self, operation: str, default_val: Any, func: Callable, *args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error {operation}: {e}")
            return default_val

    def _parse_write_response(self, response: requests.Response) -> Optional[str]:
        data = response.json()
        if 'successful' in data and data['successful']:
            first_index = list(data['successful'].keys())[0]
            return data['successful'][first_index]['key']
        if 'failed' in data and data['failed']:
            print(f"Write failed details: {data['failed']}")
        return None

    def _paginate_items(self, endpoint: str, params: Optional[Dict] = None) -> Iterator[ZoteroItem]:
        limit = 100
        start = 0
        if params is None:
            params = {}
        params['limit'] = limit

        while True:
            try:
                params['start'] = start
                response = self.http.get(endpoint, params=params)
                items = response.json()
                if not items:
                    break
                for item in items:
                    yield ZoteroItem.from_raw_zotero_item(item)
                start += len(items)
                if len(items) < limit:
                    break
            except Exception as e:
                print(f"Error fetching items from {endpoint}: {e}")
                break

    # --- Read Operations ---

    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        return self._safe_execute(
            "fetching user groups", [],
            lambda: self.http.get(f"users/{user_id}/groups", use_prefix=False).json()
        )

    def get_all_collections(self) -> List[Dict[str, Any]]:
        return self._safe_execute(
            "fetching collections", [],
            lambda: self.http.get("collections", params={'limit': 100}).json()
        )

    def get_top_collections(self) -> List[Dict[str, Any]]:
        return self._safe_execute(
            "fetching top collections", [],
            lambda: self.http.get("collections/top").json()
        )

    def get_subcollections(self, collection_key: str) -> List[Dict[str, Any]]:
        return self._safe_execute(
            f"fetching subcollections of {collection_key}", [],
            lambda: self.http.get(f"collections/{collection_key}/collections").json()
        )

    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        return self._safe_execute(
            f"fetching collection {collection_key}", None,
            lambda: self.http.get(f"collections/{collection_key}").json()
        )

    def get_tags(self) -> List[str]:
        def _fetch_tags():
            response = self.http.get("tags", params={'limit': 100})
            tags_data = response.json()
            return [t['tag'] for t in tags_data]
        return self._safe_execute("fetching tags", [], _fetch_tags)

    def get_tags_for_item(self, item_key: str) -> List[str]:
        return self._safe_execute(
            f"fetching tags for item {item_key}", [],
            lambda: [t['tag'] for t in self.http.get(f"items/{item_key}/tags").json()]
        )

    def get_tags_in_collection(self, collection_key: str) -> List[str]:
        return self._safe_execute(
            f"fetching tags in collection {collection_key}", [],
            lambda: [t['tag'] for t in self.http.get(f"collections/{collection_key}/tags").json()]
        )

    def get_saved_searches(self) -> List[Dict[str, Any]]:
        return self._safe_execute(
            "fetching saved searches", [],
            lambda: self.http.get("searches").json()
        )

    def search_items(self, query: ZoteroQuery) -> Iterator[ZoteroItem]:
        return self._paginate_items("items", params=query.to_params())

    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        return self.search_items(ZoteroQuery(tag=tag))

    def get_items_in_collection(self, collection_id: str, top_only: bool = False) -> Iterator[ZoteroItem]:
        endpoint = f"collections/{collection_id}/items"
        if top_only:
            endpoint += "/top"
        return self._paginate_items(endpoint)

    def get_trash_items(self) -> Iterator[ZoteroItem]:
        return self._paginate_items("items/trash")

    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        return self._safe_execute(
            f"fetching item {item_key}", None,
            lambda: ZoteroItem.from_raw_zotero_item(self.http.get(f"items/{item_key}").json())
        )

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        return self._safe_execute(
            f"fetching children for {item_key}", [],
            lambda: self.http.get(f"items/{item_key}/children").json()
        )

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        cols = self.get_all_collections()
        for c in cols:
            if c.get('data', {}).get('name') == name:
                return c['key']
        return None

    # --- Write Operations ---

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        payload = {"name": name}
        if parent_key:
            payload["parentCollection"] = parent_key

        try:
            response = self.http.post("collections", json_data=[payload])
            return self._parse_write_response(response)
        except Exception as e:
            print(f"Error creating collection: {e}")
            return None

    def delete_collection(self, collection_key: str, version: int) -> bool:
        try:
            response = self.http.delete(f"collections/{collection_key}", version_check=True)
            if response.status_code == 412:
                self.http.delete(f"collections/{collection_key}", version_check=True)
            return True
        except Exception as e:
            print(f"Error deleting collection {collection_key}: {e}")
            return False

    def rename_collection(self, collection_key: str, version: int, name: str) -> bool:
        try:
            self.http.patch(f"collections/{collection_key}", json_data={"name": name}, version_check=True)
            return True
        except Exception as e:
            print(f"Error renaming collection {collection_key}: {e}")
            return False

    def add_tags(self, item_key: str, tags: List[str]) -> bool:
        if not tags:
            return True
        item = self.get_item(item_key)
        if not item:
            return False

        current_tags = [t['tag'] for t in item.raw_data.get('data', {}).get('tags', [])]
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
            chunk = tags[i:i + chunk_size]
            tags_query = " || ".join(chunk)
            try:
                self.http.delete("tags", params={"tag": tags_query}, version_check=True)
            except Exception as e:
                print(f"Error deleting tags chunk: {e}")
                success = False
        return success

    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        creators = []
        for author in paper.authors:
            parts = author.rsplit(' ', 1)
            if len(parts) == 2:
                creators.append({"creatorType": "author", "firstName": parts[0], "lastName": parts[1]})
            else:
                creators.append({"creatorType": "author", "name": author})

        item_payload = {
            "itemType": "journalArticle",
            "title": paper.title,
            "abstractNote": paper.abstract,
            "creators": creators,
            "collections": [collection_id]
        }

        if paper.url:
            item_payload["url"] = paper.url
        elif paper.arxiv_id:
            item_payload["url"] = f"https://arxiv.org/abs/{paper.arxiv_id}"

        if paper.arxiv_id:
            item_payload["libraryCatalog"] = "arXiv"
            item_payload["extra"] = f"arXiv: {paper.arxiv_id}"

        if paper.doi:
            item_payload["DOI"] = paper.doi
        if paper.publication:
            item_payload["publicationTitle"] = paper.publication
        if paper.year:
            item_payload["date"] = paper.year

        try:
            response = self.http.post("items", json_data=[item_payload])
            return bool(self._parse_write_response(response))
        except Exception as e:
            print(f"Error creating item: {e}")
            return False

    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        try:
            response = self.http.post("items", json_data=[item_data])
            return self._parse_write_response(response)
        except Exception as e:
            print(f"Error creating generic item: {e}")
            return None

    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        try:
            self.http.patch(f"items/{item_key}", json_data=item_data, version_check=True)
            return True
        except Exception as e:
            print(f"Error updating item {item_key}: {e}")
            return False

    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        payload = [{
            "itemType": "note",
            "parentItem": parent_item_key,
            "note": note_content
        }]
        try:
            response = self.http.post("items", json_data=payload)
            return bool(self._parse_write_response(response))
        except Exception as e:
            print(f"Error creating note for {parent_item_key}: {e}")
            return False

    def update_note(self, note_key: str, version: int, note_content: str) -> bool:
        payload = {
            "note": note_content,
            "version": version
        }
        try:
            response = self.http.patch(f"items/{note_key}", json_data=payload, version_check=False)
            if response.status_code == 412:
                new_version = self.http.last_library_version
                payload['version'] = new_version
                self.http.patch(f"items/{note_key}", json_data=payload, version_check=False)
            return True
        except Exception as e:
            print(f"Error updating note {note_key}: {e}")
            return False

    def delete_item(self, item_key: str, version: int) -> bool:
        try:
            response = self.http.delete(f"items/{item_key}", version_check=True)
            if response.status_code == 412:
                self.http.delete(f"items/{item_key}", version_check=True)
            return True
        except Exception as e:
            print(f"Error deleting item {item_key}: {e}")
            return False

    def update_item_collections(self, item_key: str, version: int, collections: List[str]) -> bool:
        payload = {"collections": collections}
        try:
            resp = self.http.patch(f"items/{item_key}", json_data=payload, version_check=True)
            if resp.status_code == 412:
                resp = self.http.patch(f"items/{item_key}", json_data=payload, version_check=True)
            if resp.status_code != 204:
                return False
            return True
        except Exception as e:
            print(f"Error updating item {item_key} collections: {e}")
            return False

    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        return self.update_item(item_key, version, metadata)

    def upload_attachment(self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf") -> bool:
        try:
            filename = os.path.basename(file_path)
            filesize = os.path.getsize(file_path)
            mtime = int(os.path.getmtime(file_path) * 1000)

            md5_hash = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            md5 = md5_hash.hexdigest()

            # 1. Create Attachment Item placeholder
            payload = [{
                "itemType": "attachment",
                "linkMode": "imported_file",
                "parentItem": parent_item_key,
                "title": filename,
                "contentType": mime_type
            }]

            res = self.http.post("items", json_data=payload)
            attachment_key = self._parse_write_response(res)
            if not attachment_key:
                return False

            # 2. Get Upload Authorization
            auth_data = {
                "md5": md5,
                "filename": filename,
                "filesize": filesize,
                "mtime": mtime
            }
            # Important: If-None-Match: * ensures we don't overwrite if not needed
            headers = {'If-None-Match': '*', 'Content-Type': 'application/x-www-form-urlencoded'}

            # Add params=1 as query param to get upload parameters
            auth_res = self.http.post_form(f"items/{attachment_key}/file?params=1", data=auth_data, headers=headers)
            auth_resp_data = auth_res.json()

            if auth_resp_data.get('exists') == 1:
                return True

            upload_url = auth_resp_data['url']
            upload_params = auth_resp_data.get('params', {})
            upload_key = auth_resp_data.get('uploadKey')

            # 3. Perform the actual upload (typically to S3)
            with open(file_path, 'rb') as f:
                self.http.upload_file(upload_url, data=upload_params, files={'file': f})

            # 4. Register the upload with Zotero
            reg_data = {"upload": upload_key}
            reg_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            self.http.post_form(f"items/{attachment_key}/file", data=reg_data, headers=reg_headers)

            return True

        except Exception as e:
            print(f"Error uploading attachment: {e}")
            return False
