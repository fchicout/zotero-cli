import requests
from typing import Optional, Dict, Any, Union

class ZoteroHttpClient:
    """
    Low-level HTTP Client for Zotero API.
    Responsibilities:
    - Authentication (Headers)
    - Base URL construction (User vs Group)
    - Session management
    - Rate Limiting / Retries (TODO)
    - Error Handling (Basic)
    """
    API_VERSION = '3'
    BASE_URL = 'https://api.zotero.org'

    def __init__(self, api_key: str, library_id: str, library_type: str = 'group'):
        self.api_key = api_key
        self.library_id = library_id
        self.library_type = library_type
        
        self.session = requests.Session()
        self.session.headers.update({
            'Zotero-API-Version': self.API_VERSION,
            'Zotero-API-Key': self.api_key
        })
        
        # Determine prefix: /groups/123 or /users/123
        prefix = "users" if library_type == 'user' else "groups"
        self.api_prefix = f"{self.BASE_URL}/{prefix}/{self.library_id}"
        
        # State
        self.last_library_version = 0

    def get(self, endpoint: str, params: Optional[Dict] = None, use_prefix: bool = True) -> requests.Response:
        url = f"{self.api_prefix}/{endpoint}" if use_prefix else f"{self.BASE_URL}/{endpoint}"
        # Strip leading slash if present in endpoint to avoid double slash issues? 
        # requests handles it mostly, but let's be clean.
        
        response = self.session.get(url, params=params)
        self._update_version(response)
        response.raise_for_status()
        return response

    def post(self, endpoint: str, json_data: Any, use_prefix: bool = True) -> requests.Response:
        url = f"{self.api_prefix}/{endpoint}" if use_prefix else f"{self.BASE_URL}/{endpoint}"
        response = self.session.post(url, json=json_data)
        self._update_version(response)
        response.raise_for_status()
        return response

    def patch(self, endpoint: str, json_data: Any, version_check: bool = False) -> requests.Response:
        url = f"{self.api_prefix}/{endpoint}"
        headers = self.session.headers.copy()
        
        # Concurrency Control
        if version_check:
            headers['If-Unmodified-Since-Version'] = str(self.last_library_version)
        
        response = self.session.patch(url, json=json_data, headers=headers)
        
        # Simple retry logic for 412 could go here, but logic currently resides in caller.
        # For now, we return raw response for caller to handle 412.
        
        if response.status_code != 412:
            response.raise_for_status()
            
        self._update_version(response)
        return response

    def delete(self, endpoint: str, params: Optional[Dict] = None, version_check: bool = True) -> requests.Response:
        url = f"{self.api_prefix}/{endpoint}"
        headers = self.session.headers.copy()
        if version_check:
            headers['If-Unmodified-Since-Version'] = str(self.last_library_version)
            
        response = self.session.delete(url, params=params, headers=headers)
        if response.status_code != 412:
            response.raise_for_status()
            
        self._update_version(response)
        return response

    def upload_file(self, url: str, data: Dict, files: Dict) -> requests.Response:
        """
        Direct upload bypasses the Zotero Prefix, usually going to S3 or a specific upload URL.
        """
        response = requests.post(url, data=data, files=files)
        response.raise_for_status()
        return response

    def post_form(self, endpoint: str, data: Dict, headers: Optional[Dict] = None) -> requests.Response:
        """
        For multipart/form-data or urlencoded posts (like attachment authorization).
        """
        url = f"{self.api_prefix}/{endpoint}"
        h = self.session.headers.copy()
        if headers:
            h.update(headers)
            
        response = self.session.post(url, data=data, headers=h)
        response.raise_for_status()
        return response

    def _update_version(self, response: requests.Response):
        version = response.headers.get('Last-Modified-Version')
        if version:
            self.last_library_version = int(version)
