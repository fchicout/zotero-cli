"""Zotero DOI Updater - Updates missing DOIs in Zotero library.

This module extracts DOIs from the Extra field and updates the DOI field
in Zotero items, similar to the ArticleExtractor logic.
"""

import re
import requests
from typing import List, Dict, Any, Optional, Callable


class ZoteroDOIUpdaterError(Exception):
    """Base exception for Zotero DOI updater errors."""
    pass


class ZoteroConnectionError(ZoteroDOIUpdaterError):
    """Failed to connect to Zotero API."""
    pass


class ZoteroAuthenticationError(ZoteroDOIUpdaterError):
    """Invalid API key or insufficient permissions."""
    pass


class ZoteroDOIUpdater:
    """Updates missing DOIs in Zotero library by extracting from Extra field.
    
    This class connects to a Zotero library (user or group), finds items
    without DOIs, extracts DOIs from the Extra field, and updates the items.
    
    Attributes:
        api_key: Zotero API key
        library_id: User ID or Group ID
        library_type: 'user' or 'group'
    """
    
    API_VERSION = '3'
    BASE_URL = 'https://api.zotero.org'
    
    # DOI regex pattern - same as ArticleExtractor
    DOI_PATTERN = re.compile(
        r'(?:doi[:\s]+)?'  # Optional "doi:" or "DOI:" prefix
        r'(10\.\d{4,}/[^\s,;]+)',  # DOI format: 10.xxxx/...
        re.IGNORECASE
    )
    
    # Item types that support DOI field in Zotero
    ITEM_TYPES_WITH_DOI = {
        'journalArticle', 'conferencePaper', 'bookSection', 'book',
        'report', 'thesis', 'manuscript', 'preprint', 'document',
        'magazineArticle', 'newspaperArticle'
    }
    
    def __init__(self, api_key: str, library_id: str, library_type: str = 'group'):
        """Initialize Zotero DOI updater.
        
        Args:
            api_key: Zotero API key (get from https://www.zotero.org/settings/keys)
            library_id: User ID or Group ID
            library_type: 'user' or 'group' (default: 'group')
        """
        self.api_key = api_key
        self.library_id = library_id
        self.library_type = library_type
        self.headers = {
            'Zotero-API-Version': self.API_VERSION,
            'Zotero-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        self.base_url = f"{self.BASE_URL}/{library_type}s/{library_id}"
    
    def _extract_doi_from_extra(self, extra_field: str) -> str:
        """Extract DOI from the Extra field using regex.
        
        Args:
            extra_field: Content of the Extra field
            
        Returns:
            Extracted DOI string, or empty string if not found
        """
        if not extra_field:
            return ''
        
        match = self.DOI_PATTERN.search(extra_field)
        if match:
            return match.group(1).strip()
        
        return ''
    
    def test_connection(self) -> bool:
        """Test connection to Zotero API.
        
        Returns:
            True if connection successful
            
        Raises:
            ZoteroConnectionError: If cannot connect to API
            ZoteroAuthenticationError: If API key is invalid
        """
        url = f"{self.base_url}/items"
        
        try:
            response = requests.get(url, headers=self.headers, params={'limit': 1})
            
            if response.status_code == 403:
                raise ZoteroAuthenticationError(
                    "Invalid API key or insufficient permissions.\n"
                    "Please check:\n"
                    "  - Your API key is correct\n"
                    "  - The API key has read/write permissions\n"
                    "  - The library ID is correct\n"
                    "  - You have access to this library"
                )
            
            response.raise_for_status()
            return True
            
        except requests.exceptions.ConnectionError as e:
            raise ZoteroConnectionError(
                f"Cannot connect to Zotero API: {str(e)}\n"
                "Please check your internet connection."
            )
        except requests.exceptions.RequestException as e:
            raise ZoteroConnectionError(
                f"Error connecting to Zotero: {str(e)}"
            )
    
    def get_items_without_doi(self, collection_id: Optional[str] = None, 
                             limit: int = 100) -> List[Dict[str, Any]]:
        """Get items that don't have a DOI field but might have one in Extra.
        
        Args:
            collection_id: Optional collection ID to filter items
            limit: Maximum number of items to fetch (default: 100, max: 100)
            
        Returns:
            List of Zotero items without DOI
        """
        if collection_id:
            url = f"{self.base_url}/collections/{collection_id}/items"
        else:
            url = f"{self.base_url}/items"
        
        items_without_doi = []
        start = 0
        batch_limit = min(limit, 100)  # Zotero API max is 100
        
        try:
            while len(items_without_doi) < limit:
                response = requests.get(
                    url, 
                    headers=self.headers, 
                    params={'limit': batch_limit, 'start': start}
                )
                response.raise_for_status()
                items = response.json()
                
                if not items:
                    break
                
                for item in items:
                    item_type = item['data'].get('itemType', '')
                    
                    # Skip non-regular items (attachments, notes)
                    if item_type in ['attachment', 'note']:
                        continue
                    
                    # Skip item types that don't support DOI field
                    if item_type not in self.ITEM_TYPES_WITH_DOI:
                        continue
                    
                    # Check if DOI is missing
                    doi = item['data'].get('DOI', '').strip()
                    extra = item['data'].get('extra', '')
                    
                    if not doi and extra:
                        # Check if Extra contains a DOI
                        extracted_doi = self._extract_doi_from_extra(extra)
                        if extracted_doi:
                            items_without_doi.append(item)
                            
                            if len(items_without_doi) >= limit:
                                break
                
                start += len(items)
                if len(items) < batch_limit:
                    break
                    
        except requests.exceptions.RequestException as e:
            print(f"Error fetching items: {e}")
        
        return items_without_doi
    
    def update_item_doi(self, item: Dict[str, Any]) -> bool:
        """Update a single item's DOI field.
        
        Args:
            item: Zotero item dictionary
            
        Returns:
            True if update successful, False otherwise
        """
        item_key = item['key']
        extra = item['data'].get('extra', '')
        
        # Extract DOI from Extra field
        doi = self._extract_doi_from_extra(extra)
        
        if not doi:
            return False
        
        # Get fresh item data and library version
        item_url = f"{self.base_url}/items/{item_key}"
        
        try:
            # Fetch current item
            response = requests.get(item_url, headers=self.headers)
            response.raise_for_status()
            current_item = response.json()
            
            # Get library version from response header
            library_version = response.headers.get('Last-Modified-Version')
            
            # Update DOI field
            current_item['data']['DOI'] = doi
            
            # Prepare update
            url = f"{self.base_url}/items"
            headers = self.headers.copy()
            
            # Use POST to update existing items (Zotero API format)
            response = requests.post(url, headers=headers, json=[current_item])
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error updating item {item_key}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return False
    
    def update_all_dois(self, collection_id: Optional[str] = None,
                       limit: int = 100,
                       progress_callback: Optional[Callable[[int, int, str], None]] = None,
                       dry_run: bool = False) -> Dict[str, Any]:
        """Update DOIs for all items in the library or collection.
        
        Args:
            collection_id: Optional collection ID to filter items
            limit: Maximum number of items to process
            progress_callback: Optional callback for progress updates
            dry_run: If True, only report what would be updated without making changes
            
        Returns:
            Dictionary with statistics:
                - total_checked: Total items checked
                - found_dois: Items with DOIs in Extra field
                - updated: Items successfully updated
                - failed: Items that failed to update
                - skipped: Items skipped (dry run)
        """
        stats = {
            'total_checked': 0,
            'found_dois': 0,
            'updated': 0,
            'failed': 0,
            'skipped': 0
        }
        
        if progress_callback:
            progress_callback(0, 100, "Connecting to Zotero...")
        
        # Test connection
        self.test_connection()
        
        if progress_callback:
            progress_callback(10, 100, "Fetching items without DOI...")
        
        # Get items without DOI
        items = self.get_items_without_doi(collection_id, limit)
        stats['found_dois'] = len(items)
        
        if not items:
            if progress_callback:
                progress_callback(100, 100, "No items found with DOIs in Extra field")
            return stats
        
        if progress_callback:
            progress_callback(20, 100, f"Found {len(items)} items with DOIs in Extra field")
        
        # Update items
        for i, item in enumerate(items):
            stats['total_checked'] += 1
            
            title = item['data'].get('title', 'Untitled')[:50]
            extra = item['data'].get('extra', '')
            doi = self._extract_doi_from_extra(extra)
            
            if dry_run:
                stats['skipped'] += 1
                if progress_callback:
                    progress = 20 + int((i + 1) / len(items) * 80)
                    progress_callback(
                        progress, 100,
                        f"[DRY RUN] Would update: {title}... → DOI: {doi}"
                    )
            else:
                success = self.update_item_doi(item)
                
                if success:
                    stats['updated'] += 1
                    if progress_callback:
                        progress = 20 + int((i + 1) / len(items) * 80)
                        progress_callback(
                            progress, 100,
                            f"✓ Updated: {title}... → DOI: {doi}"
                        )
                else:
                    stats['failed'] += 1
                    if progress_callback:
                        progress = 20 + int((i + 1) / len(items) * 80)
                        progress_callback(
                            progress, 100,
                            f"✗ Failed: {title}..."
                        )
        
        if progress_callback:
            progress_callback(100, 100, "Update complete")
        
        return stats
