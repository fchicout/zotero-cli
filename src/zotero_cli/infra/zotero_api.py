import os
import hashlib
from typing import Optional, Iterator, Dict, Any, List
import requests

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.http_client import ZoteroHttpClient

class ZoteroAPIClient(ZoteroGateway):
    """
    Implementation of ZoteroGateway using ZoteroHttpClient.
    Focuses on Domain Object mapping (JSON -> ZoteroItem) and Business Logic.
    """

    def __init__(self, api_key: str, library_id: str, library_type: str = 'group'):
        self.http = ZoteroHttpClient(api_key, library_id, library_type)

    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        # This bypasses the instance's library context, using the raw base URL
        # We can implement a specialized method in HttpClient or just use requests here, 
        # but HttpClient has `get(use_prefix=False)` support.
        # Endpoint: /users/{user_id}/groups
        try:
            response = self.http.get(f"users/{user_id}/groups", use_prefix=False)
            return response.json()
        except Exception as e:
            print(f"Error fetching user groups: {e}")
            return []

    def get_all_collections(self) -> List[Dict[str, Any]]:
        try:
            response = self.http.get("collections", params={'limit': 100})
            return response.json()
        except Exception as e:
            print(f"Error fetching collections: {e}")
            return []

    def get_tags(self) -> List[str]:
        try:
            response = self.http.get("tags", params={'limit': 100})
            tags_data = response.json()
            return [t['tag'] for t in tags_data]
        except Exception as e:
            print(f"Error fetching tags: {e}")
            return []

    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        limit = 100
        start = 0
        while True:
            try:
                response = self.http.get("items", params={'limit': limit, 'start': start, 'tag': tag})
                items = response.json()
                if not items: break
                for item in items:
                    yield ZoteroItem.from_raw_zotero_item(item)
                start += len(items)
                if len(items) < limit: break
            except Exception as e:
                print(f"Error fetching items by tag '{tag}': {e}")
                break

    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        try:
            response = self.http.get(f"items/{item_key}")
            return ZoteroItem.from_raw_zotero_item(response.json())
        except Exception as e:
            print(f"Error fetching item {item_key}: {e}")
            return None

    def get_items_in_collection(self, collection_id: str) -> Iterator[ZoteroItem]:
        limit = 100
        start = 0
        while True:
            try:
                print(f"DEBUG: Fetching items from collection {collection_id} (start={start})")
                response = self.http.get(f"collections/{collection_id}/items", params={'limit': limit, 'start': start})
                items = response.json()
                print(f"DEBUG: Got {len(items)} items")
                
                if not items: break
                for item in items:
                    yield ZoteroItem.from_raw_zotero_item(item)
                start += len(items)
                if len(items) < limit: break
            except Exception as e:
                print(f"Error fetching items: {e}")
                break

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        try:
            response = self.http.get(f"items/{item_key}/children")
            return response.json()
        except Exception as e:
            print(f"Error fetching children for {item_key}: {e}")
            return []

    # --- Write Operations ---

    def create_collection(self, name: str) -> Optional[str]:
        payload = [{"name": name}]
        try:
            response = self.http.post("collections", json_data=payload)
            data = response.json()
            if 'successful' in data and data['successful']:
                first_key = list(data['successful'].keys())[0]
                return data['successful'][first_key]['key']
            return None
        except Exception as e:
            print(f"Error creating collection: {e}")
            return None

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
        # ... (Same mapping logic as before, abbreviated for brevity/focus) ...
        # Ideally this mapping logic should be in a `ZoteroMapper` class (SRP)
        
        if paper.url: item_payload["url"] = paper.url
        elif paper.arxiv_id: item_payload["url"] = f"https://arxiv.org/abs/{paper.arxiv_id}"
        if paper.arxiv_id:
            item_payload["libraryCatalog"] = "arXiv"
            item_payload["extra"] = f"arXiv: {paper.arxiv_id}"
        if paper.doi: item_payload["DOI"] = paper.doi
        if paper.publication: item_payload["publicationTitle"] = paper.publication
        if paper.year: item_payload["date"] = paper.year

        try:
            self.http.post("items", json_data=[item_payload])
            return True
        except Exception as e:
            print(f"Error creating item: {e}")
            return False

    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        payload = [{
            "itemType": "note",
            "parentItem": parent_item_key,
            "note": note_content
        }]
        try:
            response = self.http.post("items", json_data=payload)
            data = response.json()
            # Zotero bulk API returns 200 even if items fail. Check 'successful' block.
            if 'successful' in data and data['successful']:
                return True
            if 'failed' in data and data['failed']:
                print(f"Error: Zotero failed to create note for {parent_item_key}. Details: {data['failed']}", file=sys.stderr)
            return False
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
            # We disabled strict version check in http_client.patch based on boolean
            # Logic for 412 retry is currently not in http_client but we can add it later.
            # For now, http_client raises error if not 412 (and we assume patch handles it or we handle it here?)
            # In the refactor, http_client.patch returns response.
            
            if response.status_code == 412:
                # Retry logic
                # Update version is done by _update_version in http_client automatically on any response?
                # Yes, but we need the new version from the response to update our payload
                new_version = self.http.last_library_version
                payload['version'] = new_version
                # Retry
                self.http.patch(f"items/{note_key}", json_data=payload, version_check=False)
            
            return True
        except Exception as e:
            print(f"Error updating note {note_key}: {e}")
            return False

    def delete_item(self, item_key: str, version: int) -> bool:
        try:
            response = self.http.delete(f"items/{item_key}", version_check=True)
            if response.status_code == 412:
                # Retry
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
                # Retry once. The http.patch method updates self.last_library_version from the response headers.
                # So the next call will use the fresh version.
                resp = self.http.patch(f"items/{item_key}", json_data=payload, version_check=True)
            
            if resp.status_code != 204:
                return False
                
            return True
        except Exception as e:
            print(f"Error updating item {item_key} collections: {e}")
            return False

    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        try:
            self.http.patch(f"items/{item_key}", json_data=metadata, version_check=True)
            return True
        except Exception as e:
            print(f"Error updating item {item_key} metadata: {e}")
            return False

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        # Optimization: Don't fetch all collections every time? 
        # For now, keep logic same.
        cols = self.get_all_collections()
        for c in cols:
            if c.get('data', {}).get('name') == name:
                return c['key']
        return None

    def upload_attachment(self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf") -> bool:
        # Complex logic using http client helper
        try:
            filename = os.path.basename(file_path)
            mtime = int(os.path.getmtime(file_path) * 1000)
            md5_hash = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            md5 = md5_hash.hexdigest()

            # 1. Create Attachment Item
            payload = [{
                "itemType": "attachment",
                "linkMode": "imported_file",
                "parentItem": parent_item_key,
                "title": filename,
                "contentType": mime_type
            }]
            res = self.http.post("items", json_data=payload)
            res_data = res.json()
            if 'successful' not in res_data or not res_data['successful']: return False
            attachment_key = list(res_data['successful'].keys())[0]

            # 2. Authorization
            auth_data = {
                "md5": md5,
                "filename": filename,
                "mtime": mtime,
                "contentType": mime_type,
                "params": "1"
            }
            # Needs special headers
            headers = {'If-None-Match': '*', 'Content-Type': 'application/x-www-form-urlencoded'}
            
            # Use post_form
            auth_res = self.http.post_form(f"items/{attachment_key}/file", data=auth_data, headers=headers)
            auth_resp_data = auth_res.json()
            
            if auth_resp_data.get('exists') == 1:
                return True

            # 3. Upload
            upload_url = auth_resp_data['url']
            upload_params = auth_resp_data.get('params', {})
            upload_key = auth_resp_data.get('uploadKey')
            
            with open(file_path, 'rb') as f:
                # Direct upload via requests (bypassing api prefix)
                self.http.upload_file(upload_url, data=upload_params, files={'file': f})

            # 4. Register
            reg_data = {"upload": upload_key}
            self.http.post_form(f"items/{attachment_key}/file", data=reg_data, headers=headers)
            
            return True

        except Exception as e:
            print(f"Error uploading attachment: {e}")
            return False
