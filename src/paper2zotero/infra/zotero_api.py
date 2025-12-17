import requests
import re
from typing import Optional, Iterator, Dict, Any, List

from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.models import ResearchPaper
from paper2zotero.core.zotero_item import ZoteroItem

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

    def get_all_collections(self) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/collections"
        try:
            # Fetch all collections (pagination might be needed for very large libraries)
            response = self.session.get(url, params={'limit': 100})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching collections: {e}")
            return []

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
                response = self.session.get(url, params={'limit': limit, 'start': start})
                response.raise_for_status()
                items = response.json()
                
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
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching children for {item_key}: {e}")
            return []

    def delete_item(self, item_key: str, version: int) -> bool:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items/{item_key}"
        headers = self.session.headers.copy()
        headers['If-Match'] = str(version)
        
        try:
            response = self.session.delete(url, headers=headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error deleting item {item_key}: {e}")
            return False

    def update_item_collections(self, item_key: str, version: int, collections: List[str]) -> bool:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items/{item_key}"
        headers = self.session.headers.copy()
        headers['If-Match'] = str(version)
        
        payload = {
            "collections": collections
        }
        
        try:
            response = self.session.patch(url, headers=headers, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error updating item {item_key} collections: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return False