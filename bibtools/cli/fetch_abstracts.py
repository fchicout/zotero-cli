"""CLI for fetching missing abstracts from academic APIs and updating Zotero."""

import argparse
import sys
import os
import json
import re
import time
import urllib.request
from urllib.parse import quote

from bibtools.core.zotero_doi_updater import ZoteroDOIUpdater


def reconstruct_abstract(inverted_index):
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return None
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return ' '.join([word for pos, word in word_positions])


def fetch_abstract_openalex(doi):
    """Fetch abstract from OpenAlex API."""
    try:
        url = f"https://api.openalex.org/works/doi:{doi}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Academic Research; mailto:researcher@university.edu)'
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            abstract_inverted = data.get('abstract_inverted_index')
            if abstract_inverted:
                return reconstruct_abstract(abstract_inverted)
    except Exception:
        pass
    return None


def fetch_abstract_crossref(doi):
    """Fetch abstract from CrossRef API."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Academic Research; mailto:researcher@university.edu)'
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            abstract = data.get('message', {}).get('abstract', '')
            if abstract:
                # Remove HTML tags
                abstract = re.sub(r'<[^>]+>', '', abstract)
                return abstract.strip()
    except Exception:
        pass
    return None


def fetch_abstract_semanticscholar(doi):
    """Fetch abstract from Semantic Scholar API."""
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            return data.get('abstract')
    except Exception:
        pass
    return None


def fetch_abstract_springer(doi, api_key=None):
    """Fetch abstract from Springer API."""
    if not api_key:
        return None
    
    try:
        url = f"https://api.springernature.com/meta/v2/json?q=doi:{quote(doi)}&api_key={api_key}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            records = data.get('records', [])
            if records:
                abstract = records[0].get('abstract', '')
                if abstract:
                    # Clean HTML tags
                    abstract = re.sub(r'<[^>]+>', '', abstract)
                    return abstract.strip()
    except Exception:
        pass
    return None


def fetch_abstract_europepmc(doi):
    """Fetch abstract from Europe PMC API."""
    try:
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{quote(doi)}&format=json"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            results = data.get('resultList', {}).get('result', [])
            if results:
                return results[0].get('abstractText')
    except Exception:
        pass
    return None


def fetch_abstract_doi_org(doi):
    """Try to fetch abstract by resolving DOI and scraping publisher page."""
    try:
        # Resolve DOI
        url = f"https://doi.org/{doi}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Try common abstract patterns
            patterns = [
                r'<meta name="description" content="([^"]+)"',
                r'<meta property="og:description" content="([^"]+)"',
                r'<meta name="dc\.description" content="([^"]+)"',
                r'<div class="abstract[^"]*">.*?<p[^>]*>(.*?)</p>',
                r'<section[^>]*abstract[^>]*>.*?<p[^>]*>(.*?)</p>',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
                if match:
                    abstract = match.group(1)
                    # Clean HTML tags
                    abstract = re.sub(r'<[^>]+>', '', abstract)
                    abstract = abstract.strip()
                    # Check if it's substantial (not just keywords)
                    if len(abstract) > 100:
                        return abstract
    except Exception:
        pass
    return None


def main():
    """CLI entry point for abstract fetcher."""
    parser = argparse.ArgumentParser(
        description='Fetch missing abstracts from academic APIs and update Zotero',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be updated
  python -m bibtools.cli.fetch_abstracts --collection 6WXB8QRV --dry-run
  
  # Fetch and update abstracts
  python -m bibtools.cli.fetch_abstracts --collection 6WXB8QRV
  
  # Limit to 50 items
  python -m bibtools.cli.fetch_abstracts --collection 6WXB8QRV --limit 50

Environment Variables:
  ZOTERO_API_KEY     - Your Zotero API key
  ZOTERO_LIBRARY_ID  - Your library ID
  ZOTERO_LIBRARY_TYPE - 'user' or 'group'
        """
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        default=os.environ.get('ZOTERO_API_KEY'),
        help='Zotero API key'
    )
    
    parser.add_argument(
        '--library-id',
        type=str,
        default=os.environ.get('ZOTERO_LIBRARY_ID'),
        help='Zotero library ID'
    )
    
    parser.add_argument(
        '--library-type',
        type=str,
        choices=['user', 'group'],
        default=os.environ.get('ZOTERO_LIBRARY_TYPE', 'group'),
        help='Library type'
    )
    
    parser.add_argument(
        '--springer-api-key',
        type=str,
        default=os.environ.get('SPRINGER_API_KEY'),
        help='Springer API key (optional, get from https://dev.springernature.com/)'
    )
    
    parser.add_argument(
        '--collection',
        type=str,
        help='Collection ID to filter items'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of items to process'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making changes'
    )
    
    args = parser.parse_args()
    
    # Validate
    if not args.api_key or not args.library_id:
        print("Error: --api-key and --library-id required", file=sys.stderr)
        sys.exit(1)
    
    # Execute
    exit_code = execute_fetch(
        args.api_key,
        args.library_id,
        args.library_type,
        args.collection,
        args.limit,
        args.dry_run,
        args.springer_api_key
    )
    sys.exit(exit_code)


def execute_fetch(api_key: str, library_id: str, library_type: str,
                 collection_id: str = None, limit: int = 100,
                 dry_run: bool = False, springer_api_key: str = None) -> int:
    """Execute the abstract fetching process."""
    
    print("Zotero Abstract Fetcher")
    print("=" * 70)
    print(f"Library Type: {library_type}")
    print(f"Library ID:   {library_id}")
    if collection_id:
        print(f"Collection:   {collection_id}")
    print(f"Limit:        {limit} items")
    print(f"Mode:         {'DRY RUN (no changes)' if dry_run else 'UPDATE (will modify Zotero)'}")
    print(f"Springer API: {'Enabled' if springer_api_key else 'Disabled (use --springer-api-key)'}")
    print()
    
    # Use the DOI updater's connection logic
    updater = ZoteroDOIUpdater(api_key, library_id, library_type)
    
    def progress_callback(current: int, total: int, message: str):
        """Progress callback."""
        print(f"[{current:3d}%] {message}")
    
    try:
        print("Starting abstract fetch process...")
        print()
        
        # Fetch items without abstracts
        progress_callback(0, 100, "Connecting to Zotero...")
        progress_callback(10, 100, "Fetching items without abstracts...")
        
        # Get items
        import requests
        headers = {'Zotero-API-Key': api_key}
        
        if library_type == 'group':
            base_url = f'https://api.zotero.org/groups/{library_id}'
        else:
            base_url = f'https://api.zotero.org/users/{library_id}'
        
        # Build URL
        if collection_id:
            url = f'{base_url}/collections/{collection_id}/items?limit={limit}'
        else:
            url = f'{base_url}/items?limit={limit}'
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        items = response.json()
        
        # Filter items without abstracts but with DOIs
        items_to_fetch = []
        for item in items:
            data = item.get('data', {})
            abstract = data.get('abstractNote', '').strip()
            doi = data.get('DOI', '').strip()
            
            if not abstract and doi:
                items_to_fetch.append({
                    'key': item['key'],
                    'version': item['version'],
                    'doi': doi,
                    'title': data.get('title', 'Untitled')[:50],
                    'data': data
                })
        
        progress_callback(20, 100, f"Found {len(items_to_fetch)} items without abstracts")
        
        if not items_to_fetch:
            print()
            print("=" * 70)
            print("✓ No items need abstract updates!")
            print("=" * 70)
            return 0
        
        # Fetch abstracts
        found = 0
        failed = 0
        
        for i, item in enumerate(items_to_fetch):
            progress = 20 + int((i / len(items_to_fetch)) * 80)
            
            # Try each API in order of reliability
            abstract = None
            source = None
            
            # 1. Springer API (best for Springer content)
            if springer_api_key:
                abstract = fetch_abstract_springer(item['doi'], springer_api_key)
                if abstract:
                    source = 'Springer API'
            
            # 2. OpenAlex
            if not abstract:
                abstract = fetch_abstract_openalex(item['doi'])
                if abstract:
                    source = 'OpenAlex'
            
            # 3. CrossRef
            if not abstract:
                abstract = fetch_abstract_crossref(item['doi'])
                if abstract:
                    source = 'CrossRef'
            
            # 4. Semantic Scholar
            if not abstract:
                abstract = fetch_abstract_semanticscholar(item['doi'])
                if abstract:
                    source = 'Semantic Scholar'
            
            # 5. Europe PMC
            if not abstract:
                abstract = fetch_abstract_europepmc(item['doi'])
                if abstract:
                    source = 'Europe PMC'
            
            # 6. Direct DOI resolution (last resort - scraping)
            if not abstract:
                abstract = fetch_abstract_doi_org(item['doi'])
                if abstract:
                    source = 'DOI.org (scraped)'
            
            # Update or show result
            if abstract:
                found += 1
                if dry_run:
                    progress_callback(progress, 100, 
                        f"[DRY RUN] Would update: {item['title']}... → [{source}]")
                else:
                    # Update in Zotero
                    item['data']['abstractNote'] = abstract
                    update_url = f"{base_url}/items/{item['key']}"
                    update_headers = {
                        **headers,
                        'Content-Type': 'application/json',
                        'If-Unmodified-Since-Version': str(item['version'])
                    }
                    update_response = requests.patch(
                        update_url,
                        headers=update_headers,
                        json=item['data']
                    )
                    
                    if update_response.status_code == 204:
                        progress_callback(progress, 100, 
                            f"✓ Updated: {item['title']}... → [{source}]")
                    else:
                        failed += 1
                        progress_callback(progress, 100, 
                            f"✗ Failed: {item['title']}...")
            else:
                progress_callback(progress, 100, 
                    f"✗ Not found: {item['title']}...")
            
            # Rate limiting
            time.sleep(0.5)
        
        progress_callback(100, 100, "Fetch complete")
        
        # Display results
        print()
        print("=" * 70)
        print("✓ Abstract fetch process completed!")
        print()
        print("Statistics:")
        print(f"  Items checked:        {len(items_to_fetch)}")
        print(f"  Abstracts found:      {found}")
        print(f"  Not found:            {len(items_to_fetch) - found}")
        
        if dry_run:
            print(f"  Would be updated:     {found}")
            print()
            print("This was a DRY RUN - no changes were made.")
            print("Run without --dry-run to actually update abstracts.")
        else:
            print(f"  Successfully updated: {found - failed}")
            print(f"  Failed to update:     {failed}")
            print()
            print("Abstracts have been updated in your Zotero library!")
        
        print("=" * 70)
        print()
        
        return 0
        
    except Exception as e:
        print()
        print("=" * 70)
        print("✗ UNEXPECTED ERROR", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(f"{type(e).__name__}: {str(e)}", file=sys.stderr)
        print()
        return 99


if __name__ == '__main__':
    main()
