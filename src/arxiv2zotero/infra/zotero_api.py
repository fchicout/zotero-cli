import requests
import re
from typing import Optional

from arxiv2zotero.core.interfaces import ZoteroGateway
from arxiv2zotero.core.models import ArxivPaper

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
        # Placeholder for implementation
        pass
