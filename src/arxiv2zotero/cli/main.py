import argparse
import os
import sys
import re

from arxiv2zotero.infra.zotero_api import ZoteroAPIClient
from arxiv2zotero.infra.arxiv_lib import ArxivLibGateway
from arxiv2zotero.client import Arxiv2ZoteroClient, CollectionNotFoundError

def get_common_clients():
    """Helper to get Zotero and Arxiv clients from environment variables."""
    api_key = os.environ.get("ZOTERO_API_KEY")
    group_url = os.environ.get("ZOTERO_TARGET_GROUP")

    if not api_key:
        print("Error: ZOTERO_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    
    if not group_url:
        print("Error: ZOTERO_TARGET_GROUP environment variable not set.", file=sys.stderr)
        sys.exit(1)

    match = re.search(r'/groups/(\d+)', group_url)
    group_id = match.group(1) if match else None

    if not group_id:
        print(f"Error: Could not extract Group ID from URL: {group_url}", file=sys.stderr)
        sys.exit(1)

    zotero_gateway = ZoteroAPIClient(api_key, group_id)
    arxiv_gateway = ArxivLibGateway()
    return Arxiv2ZoteroClient(zotero_gateway, arxiv_gateway)

def add_command(args):
    """Handles the 'add' subcommand."""
    client = get_common_clients()
    try:
        success = client.add_paper(args.arxiv_id, args.abstract, args.title, args.folder)
        if success:
            print(f"Successfully added '{args.title}' to '{args.folder}'.")
        else:
            print(f"Failed to add '{args.title}' to '{args.folder}'. Check logs for details.")
            sys.exit(1)
    except CollectionNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def import_command(args):
    """Handles the 'import' subcommand."""
    client = get_common_clients()
    
    query = None
    if args.query:
        query = args.query
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                query = f.read().strip()
        except FileNotFoundError:
            print(f"Error: Query file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty(): # Check if stdin is being piped
        query = sys.stdin.read().strip()
    
    if not query:
        print("Error: No query provided. Use --query, --file, or pipe input.", file=sys.stderr)
        sys.exit(1)

    try:
        imported_count = client.import_from_query(
            query, args.folder, args.limit, args.verbose
        )
        print(f"Successfully imported {imported_count} papers to '{args.folder}'.")
    except CollectionNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="arXiv to Zotero CLI tool.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add 'add' subcommand
    add_parser = subparsers.add_parser("add", help="Add a single arXiv paper to Zotero.")
    add_parser.add_argument("--arxiv-id", required=True, help="The arXiv ID of the paper.")
    add_parser.add_argument("--title", required=True, help="The title of the paper.")
    add_parser.add_argument("--abstract", required=True, help="The abstract of the paper.")
    add_parser.add_argument("--folder", required=True, help="The Zotero collection (folder) name.")
    add_parser.set_defaults(func=add_command)

    # Add 'import' subcommand
    import_parser = subparsers.add_parser("import", help="Import multiple arXiv papers via search query to Zotero.")
    
    # Mutually exclusive group for query input
    query_group = import_parser.add_mutually_exclusive_group(required=False)
    query_group.add_argument("--query", help="The arXiv search query string.")
    query_group.add_argument("--file", help="Path to a file containing the arXiv search query string.")

    import_parser.add_argument("--limit", type=int, default=100, help="Maximum number of papers to import. Default: 100.")
    import_parser.add_argument("--folder", required=True, help="The Zotero collection (folder) name.")
    import_parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    import_parser.set_defaults(func=import_command)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()
