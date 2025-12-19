"""Command-line interface for updating DOIs in Zotero library.

This module provides a CLI for finding and updating missing DOIs
in a Zotero library by extracting them from the Extra field.
"""

import argparse
import sys
import os
from pathlib import Path

from bibtools.core.zotero_doi_updater import (
    ZoteroDOIUpdater,
    ZoteroDOIUpdaterError,
    ZoteroConnectionError,
    ZoteroAuthenticationError
)


def main():
    """CLI entry point for Zotero DOI updater.
    
    Parses command-line arguments and executes the DOI update process.
    """
    parser = argparse.ArgumentParser(
        description='Update missing DOIs in Zotero library from Extra field',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update DOIs in a group library (dry run first)
  python -m custom.cli.update_zotero_dois --api-key YOUR_KEY --library-id 12345 --library-type group --dry-run
  
  # Actually update DOIs
  python -m custom.cli.update_zotero_dois --api-key YOUR_KEY --library-id 12345 --library-type group
  
  # Update DOIs in a specific collection
  python -m custom.cli.update_zotero_dois --api-key YOUR_KEY --library-id 12345 --collection ABCD1234
  
  # Update DOIs in user library
  python -m custom.cli.update_zotero_dois --api-key YOUR_KEY --library-id 67890 --library-type user
  
  # Limit number of items to process
  python -m custom.cli.update_zotero_dois --api-key YOUR_KEY --library-id 12345 --limit 50

Environment Variables:
  ZOTERO_API_KEY     - Your Zotero API key (alternative to --api-key)
  ZOTERO_LIBRARY_ID  - Your library ID (alternative to --library-id)
  ZOTERO_LIBRARY_TYPE - 'user' or 'group' (alternative to --library-type)

Get your API key: https://www.zotero.org/settings/keys
Find your library ID: https://www.zotero.org/groups/ (in the URL)
        """
    )
    
    # Required arguments (can come from env vars)
    parser.add_argument(
        '--api-key',
        type=str,
        default=os.environ.get('ZOTERO_API_KEY'),
        help='Zotero API key (or set ZOTERO_API_KEY env var)'
    )
    
    parser.add_argument(
        '--library-id',
        type=str,
        default=os.environ.get('ZOTERO_LIBRARY_ID'),
        help='Zotero library ID - user ID or group ID (or set ZOTERO_LIBRARY_ID env var)'
    )
    
    parser.add_argument(
        '--library-type',
        type=str,
        choices=['user', 'group'],
        default=os.environ.get('ZOTERO_LIBRARY_TYPE', 'group'),
        help='Library type: user or group (default: group)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--collection',
        type=str,
        help='Collection ID to filter items (optional)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of items to process (default: 100)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    
    args = parser.parse_args()
    
    # Validate required arguments
    if not args.api_key:
        print("Error: --api-key is required (or set ZOTERO_API_KEY environment variable)", file=sys.stderr)
        print("Get your API key: https://www.zotero.org/settings/keys", file=sys.stderr)
        sys.exit(1)
    
    if not args.library_id:
        print("Error: --library-id is required (or set ZOTERO_LIBRARY_ID environment variable)", file=sys.stderr)
        print("Find your library ID in the Zotero URL (e.g., https://www.zotero.org/groups/12345)", file=sys.stderr)
        sys.exit(1)
    
    # Execute update
    exit_code = execute_update(
        args.api_key,
        args.library_id,
        args.library_type,
        args.collection,
        args.limit,
        args.dry_run
    )
    sys.exit(exit_code)


def execute_update(api_key: str, library_id: str, library_type: str,
                  collection_id: str = None, limit: int = 100,
                  dry_run: bool = False) -> int:
    """Execute the DOI update process.
    
    Args:
        api_key: Zotero API key
        library_id: Library ID
        library_type: 'user' or 'group'
        collection_id: Optional collection ID
        limit: Maximum items to process
        dry_run: If True, don't make actual changes
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Display start message
    print("Zotero DOI Updater")
    print("=" * 70)
    print(f"Library Type: {library_type}")
    print(f"Library ID:   {library_id}")
    if collection_id:
        print(f"Collection:   {collection_id}")
    print(f"Limit:        {limit} items")
    print(f"Mode:         {'DRY RUN (no changes)' if dry_run else 'UPDATE (will modify Zotero)'}")
    print()
    
    # Create updater
    updater = ZoteroDOIUpdater(api_key, library_id, library_type)
    
    def progress_callback(current: int, total: int, message: str):
        """Progress callback for reporting update progress."""
        print(f"[{current:3d}%] {message}")
    
    try:
        # Execute update
        print("Starting DOI update process...")
        print()
        
        stats = updater.update_all_dois(
            collection_id=collection_id,
            limit=limit,
            progress_callback=progress_callback,
            dry_run=dry_run
        )
        
        # Display results
        print()
        print("=" * 70)
        print("✓ Update process completed!")
        print()
        print("Statistics:")
        print(f"  Items checked:        {stats['total_checked']}")
        print(f"  DOIs found in Extra:  {stats['found_dois']}")
        
        if dry_run:
            print(f"  Would be updated:     {stats['skipped']}")
            print()
            print("This was a DRY RUN - no changes were made to Zotero.")
            print("Run without --dry-run to actually update the DOIs.")
        else:
            print(f"  Successfully updated: {stats['updated']}")
            print(f"  Failed to update:     {stats['failed']}")
            print()
            print("DOIs have been updated in your Zotero library!")
        
        print("=" * 70)
        print()
        
        return 0  # Success
        
    except ZoteroAuthenticationError as e:
        print()
        print("=" * 70)
        print("✗ AUTHENTICATION ERROR", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("Tip: Check your API key and permissions at:", file=sys.stderr)
        print("     https://www.zotero.org/settings/keys", file=sys.stderr)
        print()
        return 1
        
    except ZoteroConnectionError as e:
        print()
        print("=" * 70)
        print("✗ CONNECTION ERROR", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("Tip: Check your internet connection and try again", file=sys.stderr)
        print()
        return 2
        
    except ZoteroDOIUpdaterError as e:
        print()
        print("=" * 70)
        print("✗ UPDATE ERROR", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print()
        return 3
        
    except Exception as e:
        print()
        print("=" * 70)
        print("✗ UNEXPECTED ERROR", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(f"An unexpected error occurred: {type(e).__name__}", file=sys.stderr)
        print(f"{str(e)}", file=sys.stderr)
        print(file=sys.stderr)
        print("This may be a bug. Please report this error.", file=sys.stderr)
        print()
        return 99


if __name__ == '__main__':
    main()
