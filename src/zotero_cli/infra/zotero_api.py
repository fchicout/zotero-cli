import requests
import re
import os
import hashlib
from typing import Optional, Iterator, Dict, Any, List

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.zotero_item import ZoteroItem

class ZoteroAPIClient(ZoteroGateway):
    API_VERSION = '3'
    BASE_URL = 'https://api.zotero.org'

    def __init__(self, api_key: str, group_id: str):
        self.api_key = api_key
        self.group_id = group_id
        self.session = requests.Session()
        self.session.headers.update({
            'Zotero-API-Version': self.API_VERSION,
            'Zotero-API-Key': self.api_key
        })
        self.headers = self.session.headers
        self.last_library_version = 0

    def _update_library_version(self, response: requests.Response):
        version = response.headers.get('Last-Modified-Version')
        if version:
            self.last_library_version = int(version)

    def get_all_collections(self) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/collections"
        try:
            # Fetch all collections (pagination might be needed for very large libraries)
            response = self.session.get(url, params={'limit': 100})
            response.raise_for_status()
            self._update_library_version(response)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching collections: {e}")
            return []

    def get_tags(self) -> List[str]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/tags"
        try:
            response = self.session.get(url, params={'limit': 100}) # Pagination might be needed
            response.raise_for_status()
            tags_data = response.json()
            return [t['tag'] for t in tags_data]
        except requests.exceptions.RequestException as e:
            print(f"Error fetching tags: {e}")
            return []

    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items"
        limit = 100
        start = 0
        
        while True:
            try:
                response = self.session.get(url, params={'limit': limit, 'start': start, 'tag': tag})
                response.raise_for_status()
                self._update_library_version(response)
                items = response.json()
                
                if not items:
                    break
                    
                for item in items:
                    yield ZoteroItem.from_raw_zotero_item(item)
                
                start += len(items)
                if len(items) < limit:
                    break
            except requests.exceptions.RequestException as e:
                print(f"Error fetching items by tag '{tag}': {e}")
                break

    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items/{item_key}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            self._update_library_version(response)
            return ZoteroItem.from_raw_zotero_item(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error fetching item {item_key}: {e}")
            return None

    def upload_attachment(self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf") -> bool:
        try:
            filename = os.path.basename(file_path)
            # Calculate MD5 and mtime
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
            create_url = f"{self.BASE_URL}/groups/{self.group_id}/items"
            response = self.session.post(create_url, json=payload)
            response.raise_for_status()
            res_data = response.json()
            if 'successful' not in res_data or not res_data['successful']:
                return False
            
            attachment_key = list(res_data['successful'].keys())[0]

            # 2. Authorization
            auth_url = f"{self.BASE_URL}/groups/{self.group_id}/items/{attachment_key}/file"
            headers = self.session.headers.copy()
            headers['If-None-Match'] = '*'
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            data = {
                "md5": md5,
                "filename": filename,
                "mtime": mtime,
                "contentType": mime_type,
                "params": "1"
            }
            
            auth_res = self.session.post(auth_url, headers=headers, data=data)
            
            # If 304 Not Modified, it implies we provided If-Match and it matched, but here we used If-None-Match.
            # Zotero API returns 200 OK with exists=1 if file exists.
            auth_res.raise_for_status()
            auth_data = auth_res.json()

            if auth_data.get('exists') == 1:
                return True

            # 3. Upload
            upload_url = auth_data['url']
            upload_params = auth_data.get('params', {})
            upload_key = auth_data.get('uploadKey')
            
            with open(file_path, 'rb') as f:
                # Use bare requests to avoid Zotero headers on S3/upload URL
                # Verify if 'prefix' and 'suffix' are needed? 
                # Docs say: "Construct a POST request... containing the properties of the params object"
                # requests.post(url, data=params, files={'file': f}) does exactly this.
                upload_res = requests.post(upload_url, data=upload_params, files={'file': f})
                upload_res.raise_for_status()

            # 4. Register
            register_data = {"upload": upload_key}
            reg_res = self.session.post(auth_url, headers=headers, data=register_data)
            reg_res.raise_for_status()
            
            return True

        except Exception as e:
            print(f"Error uploading attachment: {e}")
            return False

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        collections = self.get_all_collections()
        for collection in collections:
            if collection['data']['name'] == name:
                return collection['key']
        return None

    def create_collection(self, name: str) -> Optional[str]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/collections"
        payload = [{
            "name": name
        }]
        
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if 'successful' in data and data['successful']:
                first_key = list(data['successful'].keys())[0]
                return data['successful'][first_key]['key']
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error creating collection: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return None

    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items"
        
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

        payload = [item_payload]

        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error creating item: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return False

    def get_items_in_collection(self, collection_id: str) -> Iterator[ZoteroItem]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/collections/{collection_id}/items"
        limit = 100
        start = 0
        
        while True:
            try:
                print(f"DEBUG: Fetching items from {url} (start={start})")
                response = self.session.get(url, params={'limit': limit, 'start': start})
                response.raise_for_status()
                self._update_library_version(response)
                items = response.json()
                
                print(f"DEBUG: Got {len(items)} items")
                
                if not items:
                    break
                    
                for item in items:
                    yield ZoteroItem.from_raw_zotero_item(item)
                
                start += len(items)
                if len(items) < limit:
                    break
            except requests.exceptions.RequestException as e:
                print(f"Error fetching items: {e}")
                break

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items/{item_key}/children"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            self._update_library_version(response)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching children for {item_key}: {e}")
            return []

    def delete_item(self, item_key: str, version: int) -> bool:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items/{item_key}"
        
        def _do_delete():
            headers = self.session.headers.copy()
            headers['If-Unmodified-Since-Version'] = str(self.last_library_version)
            return self.session.delete(url, headers=headers)

        try:
            response = _do_delete()
            if response.status_code == 412:
                # Precondition Failed: Library version mismatch.
                # Update version and retry once.
                self._update_library_version(response)
                response = _do_delete()
            
            response.raise_for_status()
            self._update_library_version(response)
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error deleting item {item_key}: {e}")
            return False

    def update_item_collections(self, item_key: str, version: int, collections: List[str]) -> bool:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items/{item_key}"
        headers = self.session.headers.copy()
        headers['If-Unmodified-Since-Version'] = str(self.last_library_version)
        
        payload = {
            "collections": collections
        }
        
        try:
            response = self.session.patch(url, headers=headers, json=payload)
            response.raise_for_status()
            self._update_library_version(response)
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error updating item {item_key} collections: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return False

    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items/{item_key}"
        headers = self.session.headers.copy()
        headers['If-Unmodified-Since-Version'] = str(self.last_library_version)
        
        try:
            response = self.session.patch(url, headers=headers, json=metadata)
            response.raise_for_status()
            self._update_library_version(response)
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error updating item {item_key} metadata: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return False