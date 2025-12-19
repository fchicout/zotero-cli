"""Zotero Item Reclassifier - Reclassifies items based on publication patterns.

This module identifies and reclassifies items that were incorrectly classified,
particularly conference papers that were imported as book sections.
"""

import re
import csv
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable


class ZoteroReclassifierError(Exception):
    """Base exception for reclassifier errors."""
    pass


class ZoteroItemReclassifier:
    """Reclassifies Zotero items based on publication patterns.
    
    Identifies conference papers that were incorrectly classified as book sections
    and reclassifies them to the correct type.
    """
    
    API_VERSION = '3'
    BASE_URL = 'https://api.zotero.org'
    
    # Patterns that indicate conference papers
    CONFERENCE_PATTERNS = [
        r'proceedings?\s+of',
        r'conference\s+on',
        r'international\s+conference',
        r'symposium\s+on',
        r'workshop\s+on',
        r'advances\s+in',  # Common in conference proceedings (e.g., "Advances in Knowledge Discovery")
        r'lecture\s+notes\s+in\s+computer\s+science',  # LNCS
        r'digital\s+forensics\s+and\s+cyber\s+crime',
        r'ict\s+systems\s+security',
        r'data\s+and\s+applications\s+security',
        r'neural\s+information\s+processing',
        r'euro-par\s+\d+',
        r'frontiers\s+in\s+cyber\s+security',
        r'foundations\s+and\s+practice\s+of\s+security',
        r'availability,?\s+reliability\s+and\s+security',
        r'web\s+information\s+systems\s+engineering',
        r'business\s+intelligence\s+and\s+data\s+analytics',
        r'artificial\s+intelligence\s+applications\s+and\s+innovations',
        r'machine\s+learning,?\s+optimization',
        r'cyberspace\s+simulation\s+and\s+evaluation',
        r'security\s+and\s+privacy\s+in\s+communication\s+networks',
        r'computational\s+science\s+.+\s+iccs',
        r'computer\s+security\s+.+\s+esorics',
        r'detection\s+of\s+intrusions\s+and\s+malware',
        r'risks\s+and\s+security\s+of\s+internet',
        r'testing\s+software\s+and\s+systems',
        r'information\s+and\s+communications\s+security',
        r'intelligent\s+data\s+engineering',
        r'model\s+and\s+data\s+engineering',
        r'hci\s+for\s+cybersecurity',
        r'ubiquitous\s+security',
        r'algorithms\s+and\s+architectures\s+for\s+parallel',
        r'applied\s+cryptography\s+and\s+network\s+security',
        r'security\s+and\s+trust\s+management',
        r'human\s+aspects\s+of\s+information\s+security',
        r'information\s+security\s+practice',
        r'machine\s+learning\s+for\s+networking',
        r'cyber\s+security',
        r'pattern\s+recognition\s+and\s+computer\s+vision',
        r'pervasive\s+computing\s+technologies',
        r'intelligent\s+systems\s+and\s+applications',
        r'social\s+computing\s+and\s+social\s+media',
        r'cognitive\s+computing\s+and\s+cyber\s+physical',
        r'artificial\s+intelligence\s+in\s+hci',
        r'hci\s+international',
        r'augmented\s+cognition',
        r'explainable\s+artificial\s+intelligence',
        r'disinformation\s+in\s+open\s+online\s+media',
        r'socio-technical\s+aspects\s+in\s+security',
        r'progress\s+in\s+artificial\s+intelligence',
        r'artificial\s+intelligence\s+in\s+education',
        r'quality\s+of\s+information\s+and\s+communications\s+technology',
        r'enterprise\s+design,?\s+operations',
        r'end-user\s+development',
        r'leveraging\s+applications\s+of\s+formal\s+methods',
        r'bridging\s+the\s+gap\s+between\s+ai\s+and\s+reality',
        r'safe,?\s+secure,?\s+ethical',
        r'inclusion,?\s+communication,?\s+and\s+social\s+engagement',
        r'innovative\s+computing',
        r'soft\s+computing',
        r'bio-inspired\s+computing',
        r'inventive\s+communication\s+and\s+computational',
        r'futuristic\s+trends\s+in\s+network',
        r'new\s+technologies,?\s+development\s+and\s+application',
        r'optimization\s+and\s+data\s+science',
        r'technologies\s+and\s+innovation',
        r'recent\s+trends\s+and\s+applications',
        r'data\s+science\s+and\s+communication',
        r'emerging\s+trends\s+in',
        r'advancements\s+in\s+interdisciplinary',
        r'artificial\s+intelligence\s+and\s+security',
        r'intelligent\s+strategies\s+for\s+ict',
        r'applications\s+of\s+computational\s+intelligence',
        r'intelligent\s+sustainable\s+systems',
        r'advances\s+of\s+science\s+and\s+technology',
        r'advanced\s+communication\s+and\s+intelligent\s+systems',
        r'advanced\s+intelligent\s+computing\s+technology',
        r'advanced\s+computing\s+and\s+intelligent\s+technologies',
        r'new\s+frontiers\s+in\s+artificial\s+intelligence',
        r'intelligent\s+systems$',  # Exact match to avoid false positives
        r'extended\s+reality\s+and\s+serious\s+games',
        r'natural\s+language\s+processing\s+and\s+information\s+systems',
        r'information\s+systems$',
        r'computing\s+and\s+machine\s+learning',
        r'advanced\s+information\s+networking',
        r'ict:\s+applications\s+and\s+social\s+interfaces',
        r'intersection\s+of\s+artificial\s+intelligence',
        r'secure\s+it\s+systems',
        r'international\s+joint\s+conferences',
        r'sustainable\s+innovation\s+for\s+engineering',
        r'verification,?\s+model\s+checking',
        r'knowledge\s+science,?\s+engineering\s+and\s+management',
        r'neural-symbolic\s+learning',
        r'ai,?\s+data,?\s+and\s+digitalization',
        r'intelligent\s+information\s+and\s+database\s+systems',
        r'advances\s+on\s+intelligent\s+computing',
        r'network\s+simulation\s+and\s+evaluation',
        r'data\s+science:\s+foundations',
        r'business\s+intelligence\s+and\s+information\s+technology',
        r'data\s+security\s+and\s+privacy\s+protection',
        r'computer\s+applications\s+in\s+industry',
        r'data\s+science$',
        r'information\s+systems\s+for\s+intelligent\s+systems',
        r'intelligent\s+and\s+fuzzy\s+systems',
        r'intelligent\s+computing\s+and\s+optimization',
        r'advances\s+and\s+trends\s+in\s+artificial\s+intelligence',
        r'security\s+and\s+privacy\s+in\s+cyber-physical',
        r'computer\s+science\s+–\s+cacic',
        r'integration\s+of\s+artificial\s+intelligence\s+in\s+iot',
        r'artificial\s+intelligence\s+and\s+machine\s+learning',
        r'artificial\s+intelligence\s+based\s+smart',
        r'computer\s+vision\s+and\s+robotics',
        r'artificial\s+neural\s+networks\s+and\s+machine\s+learning',
        r'technologies\s+and\s+applications\s+of\s+artificial\s+intelligence',
        r'innovations\s+in\s+computational\s+intelligence',
        r'foundations\s+of\s+computer\s+science',
        r'big\s+data\s+analytics\s+in\s+astronomy',
        r'security\s+and\s+privacy\s+in\s+social\s+networks',
        r'software,?\s+system,?\s+and\s+service\s+engineering',
        r'information\s+security$',
        r'intelligent\s+systems\s+and\s+pattern\s+recognition',
        r'information\s+management\s+and\s+big\s+data',
        r'cybersecurity$',
        r'software\s+engineering:\s+emerging\s+trends',
        r'data\s+science\s+and\s+artificial\s+intelligence',
        r'digital\s+ecosystems',
        r'innovations\s+for\s+community\s+services',
        r'distributed\s+computing\s+and\s+intelligent\s+technology',
        r'technological\s+innovation\s+for\s+ai-powered',
        r'computational\s+and\s+experimental\s+simulations',
        r'social\s+networks\s+analysis\s+and\s+mining',
        r'transfer,?\s+diffusion\s+and\s+adoption',
        r'information\s+security\s+and\s+cryptology',
        r'new\s+trends\s+in\s+disruptive\s+technologies',
        r'innovations\s+in\s+cybersecurity',
        r'blockchain,?\s+metaverse\s+and\s+trustworthy',
        r'intelligent\s+computing$',
        r'database\s+systems\s+for\s+advanced\s+applications',
        r'developments\s+and\s+applications\s+in\s+smartrail',
        r'intelligent\s+technology\s+for\s+educational',
        r'web\s+information\s+systems\s+and\s+applications',
        r'computer\s+applications$',
        r'cyber-physical\s+systems\s+and\s+control',
        r'artificial\s+intelligence\s+and\s+applications',
        r'signal\s+and\s+information\s+processing',
        r'biologically\s+inspired\s+cognitive\s+architectures',
        r'applied\s+intelligence\s+and\s+informatics',
        r'design\s+science\s+research',
        r'enterprise\s+applications,?\s+markets\s+and\s+services',
        r'internet\s+of\s+things\.',
        r'recent\s+challenges\s+in\s+intelligent\s+information',
        r'towards\s+digitally\s+transforming',
        r'security\s+and\s+information\s+technologies\s+with\s+ai',
        r'construction\s+applications\s+of\s+virtual\s+reality',
        r'information\s+processing\s+and\s+network\s+provisioning',
        r'networks\s+and\s+sustainability',
        r'advanced\s+information\s+systems\s+engineering',
        r'computer\s+safety,?\s+reliability,?\s+and\s+security',
        r'electronic\s+government',
        r'computation\s+of\s+artificial\s+intelligence',
        r'artificial\s+intelligence\s+in\s+healthcare',
        r'intelligent\s+systems\s+and\s+sustainable\s+computing',
        r'sustainability\s+and\s+financial\s+services',
        r'digital\s+business\s+and\s+intelligent\s+systems',
        r'frontiers\s+of\s+artificial\s+intelligence',
        r'data\s+analytics\s+and\s+management',
        r'human\s+choice\s+and\s+computers',
        r'e-infrastructure\s+and\s+e-services',
        r'wireless\s+artificial\s+intelligent\s+computing',
        r'pattern\s+recognition$',
        r'advances\s+on\s+broad-band\s+wireless',
        r'machine\s+learning\s+and\s+knowledge\s+extraction',
        r'information\s+and\s+software\s+technologies',
        r'digital\s+forensics\s+and\s+watermarking',
    ]
    
    def __init__(self, api_key: str, library_id: str, library_type: str = 'group'):
        """Initialize reclassifier.
        
        Args:
            api_key: Zotero API key
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
    
    def test_connection(self) -> bool:
        """Test connection to Zotero API."""
        url = f"{self.base_url}/items"
        try:
            response = requests.get(url, headers=self.headers, params={'limit': 1})
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
    
    def _is_conference_paper(self, item: Dict[str, Any]) -> bool:
        """Check if an item appears to be a conference paper.
        
        Args:
            item: Zotero item dictionary
            
        Returns:
            True if item appears to be a conference paper
        """
        # Get publication title
        pub_title = item['data'].get('publicationTitle', '').lower()
        book_title = item['data'].get('bookTitle', '').lower()
        series = item['data'].get('series', '').lower()
        
        # Check all title fields
        all_titles = f"{pub_title} {book_title} {series}"
        
        # Check against patterns
        for pattern in self.CONFERENCE_PATTERNS:
            if re.search(pattern, all_titles, re.IGNORECASE):
                return True
        
        return False
    
    def find_misclassified_items(self, collection_id: Optional[str] = None,
                                limit: int = 100) -> List[Dict[str, Any]]:
        """Find book sections that should be conference papers.
        
        Args:
            collection_id: Optional collection ID to filter items
            limit: Maximum number of items to check
            
        Returns:
            List of items that should be reclassified
        """
        if collection_id:
            url = f"{self.base_url}/collections/{collection_id}/items"
        else:
            url = f"{self.base_url}/items"
        
        misclassified = []
        start = 0
        batch_limit = min(limit, 100)
        
        try:
            while len(misclassified) < limit:
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
                    # Only check book sections
                    if item['data'].get('itemType') != 'bookSection':
                        continue
                    
                    # Check if it's actually a conference paper
                    if self._is_conference_paper(item):
                        misclassified.append(item)
                        
                        if len(misclassified) >= limit:
                            break
                
                start += len(items)
                if len(items) < batch_limit:
                    break
        
        except requests.exceptions.RequestException as e:
            print(f"Error fetching items: {e}")
        
        return misclassified
    
    def reclassify_item(self, item: Dict[str, Any]) -> bool:
        """Reclassify a single item from bookSection to conferencePaper.
        
        Args:
            item: Zotero item dictionary
            
        Returns:
            True if reclassification successful
        """
        item_key = item['key']
        
        # Get fresh item data
        item_url = f"{self.base_url}/items/{item_key}"
        
        try:
            # Fetch current item
            response = requests.get(item_url, headers=self.headers)
            response.raise_for_status()
            current_item = response.json()
            
            # Change item type
            old_type = current_item['data']['itemType']
            current_item['data']['itemType'] = 'conferencePaper'
            
            # Map fields from bookSection to conferencePaper
            # bookTitle → proceedingsTitle
            if 'bookTitle' in current_item['data']:
                current_item['data']['proceedingsTitle'] = current_item['data'].pop('bookTitle')
            
            # publicationTitle → proceedingsTitle (if bookTitle not present)
            if 'publicationTitle' in current_item['data'] and 'proceedingsTitle' not in current_item['data']:
                current_item['data']['proceedingsTitle'] = current_item['data'].pop('publicationTitle')
            
            # Update via API
            url = f"{self.base_url}/items"
            response = requests.post(url, headers=self.headers, json=[current_item])
            response.raise_for_status()
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error reclassifying item {item_key}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return False
    
    def reclassify_all(self, collection_id: Optional[str] = None,
                      limit: int = 100,
                      progress_callback: Optional[Callable[[int, int, str], None]] = None,
                      dry_run: bool = False) -> Dict[str, Any]:
        """Reclassify all misclassified items.
        
        Args:
            collection_id: Optional collection ID to filter items
            limit: Maximum number of items to process
            progress_callback: Optional callback for progress updates
            dry_run: If True, only report what would be changed
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_checked': 0,
            'found_misclassified': 0,
            'reclassified': 0,
            'failed': 0,
            'skipped': 0
        }
        
        if progress_callback:
            progress_callback(0, 100, "Connecting to Zotero...")
        
        # Test connection
        if not self.test_connection():
            raise ZoteroReclassifierError("Failed to connect to Zotero")
        
        if progress_callback:
            progress_callback(10, 100, "Finding misclassified items...")
        
        # Find misclassified items
        items = self.find_misclassified_items(collection_id, limit)
        stats['found_misclassified'] = len(items)
        
        if not items:
            if progress_callback:
                progress_callback(100, 100, "No misclassified items found")
            return stats
        
        if progress_callback:
            progress_callback(20, 100, f"Found {len(items)} items to reclassify")
        
        # Reclassify items
        for i, item in enumerate(items):
            stats['total_checked'] += 1
            
            title = item['data'].get('title', 'Untitled')[:50]
            pub_title = item['data'].get('publicationTitle', '') or item['data'].get('bookTitle', '')
            
            if dry_run:
                stats['skipped'] += 1
                if progress_callback:
                    progress = 20 + int((i + 1) / len(items) * 80)
                    progress_callback(
                        progress, 100,
                        f"[DRY RUN] Would reclassify: {title}... ({pub_title[:30]}...)"
                    )
            else:
                success = self.reclassify_item(item)
                
                if success:
                    stats['reclassified'] += 1
                    if progress_callback:
                        progress = 20 + int((i + 1) / len(items) * 80)
                        progress_callback(
                            progress, 100,
                            f"✓ Reclassified: {title}..."
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
            progress_callback(100, 100, "Reclassification complete")
        
        return stats
    
    def reclassify_from_csv(self, csv_path: str, collection_id: Optional[str] = None,
                           progress_callback: Optional[Callable[[int, int, str], None]] = None,
                           dry_run: bool = False) -> Dict[str, Any]:
        """Reclassify items based on Content Type from original CSV.
        
        This is the definitive method - uses the CSV as source of truth.
        
        Args:
            csv_path: Path to the original Springer CSV file
            collection_id: Optional collection ID to filter items
            progress_callback: Optional callback for progress updates
            dry_run: If True, only report what would be changed
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_checked': 0,
            'found_misclassified': 0,
            'reclassified': 0,
            'failed': 0,
            'skipped': 0,
            'csv_not_found': 0
        }
        
        if progress_callback:
            progress_callback(0, 100, "Loading CSV...")
        
        # Load CSV data
        csv_data = {}
        try:
            import html
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    doi = row.get('Item DOI', '').strip()
                    title = row.get('Item Title', '').strip()
                    content_type = row.get('Content Type', '').strip()
                    
                    # Normalize title (decode HTML entities, lowercase, remove extra spaces)
                    normalized_title = html.unescape(title).lower().strip()
                    normalized_title = ' '.join(normalized_title.split())  # Remove extra whitespace
                    
                    # Use DOI as primary key, title as fallback
                    if doi:
                        csv_data[doi] = {
                            'content_type': content_type,
                            'title': title
                        }
                    if normalized_title:
                        csv_data[normalized_title] = {
                            'content_type': content_type,
                            'title': title
                        }
        except Exception as e:
            raise ZoteroReclassifierError(f"Failed to read CSV: {e}")
        
        if progress_callback:
            progress_callback(10, 100, f"Loaded {len(csv_data)} entries from CSV")
        
        # Test connection
        if not self.test_connection():
            raise ZoteroReclassifierError("Failed to connect to Zotero")
        
        if progress_callback:
            progress_callback(20, 100, "Fetching items from Zotero...")
        
        # Get all items from collection
        if collection_id:
            url = f"{self.base_url}/collections/{collection_id}/items"
        else:
            url = f"{self.base_url}/items"
        
        items_to_reclassify = []
        start = 0
        
        while True:
            response = requests.get(
                url,
                headers=self.headers,
                params={'limit': 100, 'start': start}
            )
            response.raise_for_status()
            items = response.json()
            
            if not items:
                break
            
            for item in items:
                stats['total_checked'] += 1
                
                # Skip non-regular items
                item_type = item['data'].get('itemType', '')
                if item_type in ['attachment', 'note']:
                    continue
                
                # Get item info
                title = item['data'].get('title', '').strip()
                doi = item['data'].get('DOI', '').strip()
                
                # Normalize title for matching
                normalized_title = title.lower().strip()
                normalized_title = ' '.join(normalized_title.split())  # Remove extra whitespace
                
                # Look up in CSV
                csv_entry = None
                if doi and doi in csv_data:
                    csv_entry = csv_data[doi]
                elif normalized_title and normalized_title in csv_data:
                    csv_entry = csv_data[normalized_title]
                
                if not csv_entry:
                    stats['csv_not_found'] += 1
                    continue
                
                # Check if needs reclassification
                content_type = csv_entry['content_type'].lower()
                
                # Map content type to Zotero item type
                target_type = None
                if 'conference' in content_type and item_type == 'bookSection':
                    target_type = 'conferencePaper'
                elif 'article' in content_type and item_type == 'bookSection':
                    target_type = 'journalArticle'
                
                if target_type:
                    items_to_reclassify.append({
                        'item': item,
                        'target_type': target_type,
                        'csv_content_type': csv_entry['content_type']
                    })
            
            start += len(items)
            if len(items) < 100:
                break
        
        stats['found_misclassified'] = len(items_to_reclassify)
        
        if not items_to_reclassify:
            if progress_callback:
                progress_callback(100, 100, "No misclassified items found")
            return stats
        
        if progress_callback:
            progress_callback(30, 100, f"Found {len(items_to_reclassify)} items to reclassify")
        
        # Reclassify items
        for i, entry in enumerate(items_to_reclassify):
            item = entry['item']
            target_type = entry['target_type']
            csv_content_type = entry['csv_content_type']
            
            title = item['data'].get('title', 'Untitled')[:50]
            
            if dry_run:
                stats['skipped'] += 1
                if progress_callback:
                    progress = 30 + int((i + 1) / len(items_to_reclassify) * 70)
                    progress_callback(
                        progress, 100,
                        f"[DRY RUN] Would reclassify: {title}... (CSV: {csv_content_type})"
                    )
            else:
                # Reclassify
                success = self._reclassify_to_type(item, target_type)
                
                if success:
                    stats['reclassified'] += 1
                    if progress_callback:
                        progress = 30 + int((i + 1) / len(items_to_reclassify) * 70)
                        progress_callback(
                            progress, 100,
                            f"✓ Reclassified: {title}... → {target_type}"
                        )
                else:
                    stats['failed'] += 1
                    if progress_callback:
                        progress = 30 + int((i + 1) / len(items_to_reclassify) * 70)
                        progress_callback(
                            progress, 100,
                            f"✗ Failed: {title}..."
                        )
        
        if progress_callback:
            progress_callback(100, 100, "Reclassification complete")
        
        return stats
    
    def _reclassify_to_type(self, item: Dict[str, Any], target_type: str) -> bool:
        """Reclassify item to specific type.
        
        Args:
            item: Zotero item dictionary
            target_type: Target item type (e.g., 'conferencePaper', 'journalArticle')
            
        Returns:
            True if successful
        """
        item_key = item['key']
        
        # Get fresh item data
        item_url = f"{self.base_url}/items/{item_key}"
        
        try:
            response = requests.get(item_url, headers=self.headers)
            response.raise_for_status()
            current_item = response.json()
            
            # Change item type
            current_item['data']['itemType'] = target_type
            
            # Map fields based on target type
            if target_type == 'conferencePaper':
                # bookTitle → proceedingsTitle
                if 'bookTitle' in current_item['data']:
                    current_item['data']['proceedingsTitle'] = current_item['data'].pop('bookTitle')
                
                # publicationTitle → proceedingsTitle (if bookTitle not present)
                if 'publicationTitle' in current_item['data'] and 'proceedingsTitle' not in current_item['data']:
                    current_item['data']['proceedingsTitle'] = current_item['data'].pop('publicationTitle')
            
            elif target_type == 'journalArticle':
                # bookTitle → publicationTitle
                if 'bookTitle' in current_item['data']:
                    current_item['data']['publicationTitle'] = current_item['data'].pop('bookTitle')
            
            # Update via API
            url = f"{self.base_url}/items"
            response = requests.post(url, headers=self.headers, json=[current_item])
            response.raise_for_status()
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error reclassifying item {item_key}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return False
