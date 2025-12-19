"""CLI for reclassifying Zotero items (bookSection → conferencePaper)."""

import argparse
import sys
import os

from bibtools.core.zotero_item_reclassifier import (
    ZoteroItemReclassifier,
    ZoteroReclassifierError
)


def main():
    """CLI entry point for Zotero item reclassifier."""
    parser = argparse.ArgumentParser(
        description='Reclassify book sections that are actually conference papers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be reclassified
  python -m custom.cli.reclassify_zotero_items --collection 6WXB8QRV --dry-run
  
  # Reclassify items in raw_springer collection
  python -m custom.cli.reclassify_zotero_items --collection 6WXB8QRV
  
  # Reclassify with limit
  python -m custom.cli.reclassify_zotero_items --collection 6WXB8QRV --limit 50

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
    
    parser.add_argument(
        '--csv',
        type=str,
        help='Path to original CSV file (uses CSV Content Type as source of truth)'
    )
    
    args = parser.parse_args()
    
    # Validate
    if not args.api_key or not args.library_id:
        print("Error: --api-key and --library-id required", file=sys.stderr)
        sys.exit(1)
    
    # Execute
    exit_code = execute_reclassification(
        args.api_key,
        args.library_id,
        args.library_type,
        args.collection,
        args.limit,
        args.dry_run,
        args.csv
    )
    sys.exit(exit_code)


def execute_reclassification(api_key: str, library_id: str, library_type: str,
                             collection_id: str = None, limit: int = 100,
                             dry_run: bool = False, csv_path: str = None) -> int:
    """Execute the reclassification process."""
    
    print("Zotero Item Reclassifier")
    print("=" * 70)
    print(f"Library Type: {library_type}")
    print(f"Library ID:   {library_id}")
    if collection_id:
        print(f"Collection:   {collection_id}")
    if csv_path:
        print(f"CSV Source:   {csv_path}")
        print(f"Method:       CSV-based (uses Content Type from CSV)")
        print(f"Limit:        ALL items (CSV method ignores limit)")
    else:
        print(f"Method:       Pattern-based (uses publication title patterns)")
        print(f"Limit:        {limit} items")
    print(f"Mode:         {'DRY RUN (no changes)' if dry_run else 'RECLASSIFY (will modify Zotero)'}")
    print()
    
    # Create reclassifier
    reclassifier = ZoteroItemReclassifier(api_key, library_id, library_type)
    
    def progress_callback(current: int, total: int, message: str):
        """Progress callback."""
        print(f"[{current:3d}%] {message}")
    
    try:
        print("Starting reclassification process...")
        print()
        
        # Use CSV-based method if CSV provided
        if csv_path:
            stats = reclassifier.reclassify_from_csv(
                csv_path=csv_path,
                collection_id=collection_id,
                progress_callback=progress_callback,
                dry_run=dry_run
            )
        else:
            stats = reclassifier.reclassify_all(
                collection_id=collection_id,
                limit=limit,
                progress_callback=progress_callback,
                dry_run=dry_run
            )
        
        # Display results
        print()
        print("=" * 70)
        print("✓ Reclassification process completed!")
        print()
        print("Statistics:")
        print(f"  Items checked:          {stats['total_checked']}")
        print(f"  Misclassified found:    {stats['found_misclassified']}")
        if csv_path and stats.get('csv_not_found', 0) > 0:
            print(f"  Not found in CSV:       {stats['csv_not_found']}")
        
        if dry_run:
            print(f"  Would be reclassified:  {stats['skipped']}")
            print()
            print("This was a DRY RUN - no changes were made.")
            print("Run without --dry-run to actually reclassify items.")
        else:
            print(f"  Successfully reclassified: {stats['reclassified']}")
            print(f"  Failed to reclassify:      {stats['failed']}")
            print()
            print("Items have been reclassified in your Zotero library!")
        
        print("=" * 70)
        print()
        
        return 0
        
    except ZoteroReclassifierError as e:
        print()
        print("=" * 70)
        print("✗ RECLASSIFICATION ERROR", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print()
        return 1
        
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
