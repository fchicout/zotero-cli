import requests
import re
from typing import Optional

from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.models import ArxivPaper

class ZoteroAPIClient(ZoteroGateway):
    API_VERSION = '3'
    BASE_URL = 'https://api.zotero.org'

    def __init__(self, api_key: str, group_id: str):
        self.api_key = api_key
        self.group_id = group_id
        self.headers = {
            'Zotero-API-Version': self.API_VERSION,
            'Zotero-API-Key': self.api_key
        }

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        url = f"{self.BASE_URL}/groups/{self.group_id}/collections"
        try:
            # Fetch all collections (might need pagination for large libraries, but standard limit is usually enough for top-level)
            response = requests.get(url, headers=self.headers, params={'limit': 100})
            response.raise_for_status()
            collections = response.json()
            
            for collection in collections:
                if collection['data']['name'] == name:
                    return collection['key']
            
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching collections: {e}")
            return None

    def create_item(self, paper: ArxivPaper, collection_id: str) -> bool:
        url = f"{self.BASE_URL}/groups/{self.group_id}/items"
        
        # Construct the Zotero item payload
        # Using 'journalArticle' as a generic type for papers. 
        # Zotero also has 'preprint' type, but journalArticle is widely supported.
        payload = [{
            "itemType": "journalArticle",
            "title": paper.title,
            "abstractNote": paper.abstract,
            "url": f"https://arxiv.org/abs/{paper.arxiv_id}",
            "libraryCatalog": "arXiv",
            "accessDate": "", # Zotero will auto-fill or we can set current date
            "collections": [collection_id]
        }]

        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            # Zotero API returns the created items in the response
            # We can check if 'successful' key exists or just rely on status code
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error creating item: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return False
