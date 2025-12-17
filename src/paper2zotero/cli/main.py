import argparse
import os
import sys
import re

from paper2zotero.infra.zotero_api import ZoteroAPIClient
from paper2zotero.infra.arxiv_lib import ArxivLibGateway
from paper2zotero.infra.bibtex_lib import BibtexLibGateway
from paper2zotero.infra.ris_lib import RisLibGateway
from paper2zotero.infra.springer_csv_lib import SpringerCsvLibGateway
from paper2zotero.infra.ieee_csv_lib import IeeeCsvLibGateway
from paper2zotero.client import PaperImporterClient, CollectionNotFoundError
from paper2zotero.core.services.collection_service import CollectionService
from paper2zotero.core.services.audit_service import CollectionAuditor # Import CollectionAuditor
from paper2zotero.core.services.duplicate_service import DuplicateFinder
from paper2zotero.infra.crossref_api import CrossRefAPIClient
from paper2zotero.infra.semantic_scholar_api import SemanticScholarAPIClient 
from paper2zotero.infra.unpaywall_api import UnpaywallAPIClient # Import UnpaywallAPIClient
from paper2zotero.core.services.graph_service import CitationGraphService
from paper2zotero.core.services.metadata_aggregator import MetadataAggregatorService 

def get_zotero_gateway():
    """Helper to get Zotero client from environment variables."""
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

    return ZoteroAPIClient(api_key, group_id)

def get_common_clients():
    """Helper to get Zotero and Arxiv clients from environment variables."""
    zotero_gateway = get_zotero_gateway()
    arxiv_gateway = ArxivLibGateway()
    bibtex_gateway = BibtexLibGateway()
    ris_gateway = RisLibGateway()
    springer_csv_gateway = SpringerCsvLibGateway()
    ieee_csv_gateway = IeeeCsvLibGateway()
    return PaperImporterClient(zotero_gateway, arxiv_gateway, bibtex_gateway, ris_gateway, springer_csv_gateway, ieee_csv_gateway)

def move_command(args):
    """Handles the 'move' subcommand."""
    gateway = get_zotero_gateway()
    service = CollectionService(gateway)
    
    success = service.move_item(args.from_col, args.to_col, args.id)
    if success:
        print(f"Successfully moved item '{args.id}' from '{args.from_col}' to '{args.to_col}'.")
    else:
        print(f"Failed to move item '{args.id}'. Check if it exists in the source collection.")
        sys.exit(1)

def audit_command(args):
    """Handles the 'audit' subcommand."""
    gateway = get_zotero_gateway()
    auditor = CollectionAuditor(gateway)

    report = auditor.audit_collection(args.collection)
    if report:
        print(f"Audit Report for collection '{args.collection}':")
        print(f"  Total items: {report.total_items}")
        if report.items_missing_id:
            print(f"  Items missing ID (DOI/arXiv): {len(report.items_missing_id)}")
            for item in report.items_missing_id:
                print(f"    - {item.title} (Key: {item.key})")
        if report.items_missing_title:
            print(f"  Items missing Title: {len(report.items_missing_title)}")
            for item in report.items_missing_title:
                print(f"    - (Key: {item.key})")
        if report.items_missing_abstract:
            print(f"  Items missing Abstract: {len(report.items_missing_abstract)}")
            for item in report.items_missing_abstract:
                print(f"    - {item.title} (Key: {item.key})")
        if report.items_missing_pdf:
            print(f"  Items missing PDF attachment: {len(report.items_missing_pdf)}")
            for item in report.items_missing_pdf:
                print(f"    - {item.title} (Key: {item.key})")
    else:
        sys.exit(1)

def duplicates_command(args):
    """Handles the 'duplicates' subcommand."""
    gateway = get_zotero_gateway()
    finder = DuplicateFinder(gateway)
    
    collection_names = [name.strip() for name in args.collections.split(',')]
    duplicate_groups = finder.find_duplicates(collection_names)

    if duplicate_groups:
        print(f"Found {len(duplicate_groups)} duplicate groups across collections: {', '.join(collection_names)}")
        for i, group in enumerate(duplicate_groups):
            print(f"\nGroup {i+1}: {group.identifier_key}")
            for item in group.items:
                title_display = item.title if item.title else "(No Title)"
                print(f"  - Key: {item.key}, Title: '{title_display}', DOI: {item.doi if item.doi else 'N/A'}, ArXiv ID: {item.arxiv_id if item.arxiv_id else 'N/A'}")
    else:
        print(f"No duplicate items found across collections: {', '.join(collection_names)}")

def graph_command(args):
    """Handles the 'graph' subcommand."""
    zotero_gateway = get_zotero_gateway()
    
    # Instantiate providers
    crossref_provider = CrossRefAPIClient()
    semantic_scholar_provider = SemanticScholarAPIClient()
    unpaywall_provider = UnpaywallAPIClient()
    
    # Create aggregator
    metadata_aggregator = MetadataAggregatorService([semantic_scholar_provider, crossref_provider, unpaywall_provider])
    
    graph_service = CitationGraphService(zotero_gateway, metadata_aggregator)

    collection_names = [name.strip() for name in args.collections.split(',')]
    dot_string = graph_service.build_graph(collection_names)
    print(dot_string)

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

def bibtex_command(args):
    """Handles the 'bibtex' subcommand."""
    client = get_common_clients()
    try:
        imported_count = client.import_from_bibtex(args.file, args.folder, args.verbose)
        print(f"Successfully imported {imported_count} papers from '{args.file}' to '{args.folder}'.")
    except FileNotFoundError:
        print(f"Error: BibTeX file '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)
    except CollectionNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def ris_command(args):
    """Handles the 'ris' subcommand."""
    client = get_common_clients()
    try:
        imported_count = client.import_from_ris(args.file, args.folder, args.verbose)
        print(f"Successfully imported {imported_count} papers from '{args.file}' to '{args.folder}'.")
    except FileNotFoundError:
        print(f"Error: RIS file '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)
    except CollectionNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def springer_csv_command(args):
    """Handles the 'springer-csv' subcommand."""
    client = get_common_clients()
    try:
        imported_count = client.import_from_springer_csv(args.file, args.folder, args.verbose)
        print(f"Successfully imported {imported_count} papers from '{args.file}' to '{args.folder}'.")
    except FileNotFoundError:
        print(f"Error: Springer CSV file '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)
    except CollectionNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def ieee_csv_command(args):
    """Handles the 'ieee-csv' subcommand."""
    client = get_common_clients()
    try:
        imported_count = client.import_from_ieee_csv(args.file, args.folder, args.verbose)
        print(f"Successfully imported {imported_count} papers from '{args.file}' to '{args.folder}'.")
    except FileNotFoundError:
        print(f"Error: IEEE CSV file '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)
    except CollectionNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def remove_attachments_command(args):
    """Handles the 'remove-attachments' subcommand."""
    client = get_common_clients()
    try:
        count = client.remove_attachments_from_folder(args.folder, args.verbose)
        print(f"Successfully deleted {count} attachments from '{args.folder}'.")
    except CollectionNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def list_collections_command(args):
    """Handles the 'list-collections' subcommand."""
    gateway = get_zotero_gateway()
    collections = gateway.get_all_collections()
    if collections:
        print(f"Found {len(collections)} collections:")
        for col in collections:
            num_items = col.get('meta', {}).get('numItems', '?')
            print(f"  - {col['data']['name']} (Key: {col['key']}, Items: {num_items})")
    else:
        print("No collections found or error occurred.")

def main():
    parser = argparse.ArgumentParser(description="Paper to Zotero CLI tool.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add 'list-collections' subcommand
    list_collections_parser = subparsers.add_parser("list-collections", help="List all Zotero collections.")
    list_collections_parser.set_defaults(func=list_collections_command)

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

    # Add 'bibtex' subcommand
    bibtex_parser = subparsers.add_parser("bibtex", help="Import papers from a BibTeX file to Zotero.")
    bibtex_parser.add_argument("--file", required=True, help="Path to the BibTeX (.bib) file.")
    bibtex_parser.add_argument("--folder", required=True, help="The Zotero collection (folder) name.")
    bibtex_parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    bibtex_parser.set_defaults(func=bibtex_command)

    # Add 'ris' subcommand
    ris_parser = subparsers.add_parser("ris", help="Import papers from a RIS (.ris) file to Zotero.")
    ris_parser.add_argument("--file", required=True, help="Path to the RIS (.ris) file.")
    ris_parser.add_argument("--folder", required=True, help="The Zotero collection (folder) name.")
    ris_parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    ris_parser.set_defaults(func=ris_command)

    # Add 'springer-csv' subcommand
    springer_csv_parser = subparsers.add_parser("springer-csv", help="Import papers from a Springer CSV file to Zotero.")
    springer_csv_parser.add_argument("--file", required=True, help="Path to the Springer CSV (.csv) file.")
    springer_csv_parser.add_argument("--folder", required=True, help="The Zotero collection (folder) name.")
    springer_csv_parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    springer_csv_parser.set_defaults(func=springer_csv_command)

    # Add 'ieee-csv' subcommand
    ieee_csv_parser = subparsers.add_parser("ieee-csv", help="Import papers from an IEEE CSV file to Zotero.")
    ieee_csv_parser.add_argument("--file", required=True, help="Path to the IEEE CSV (.csv) file.")
    ieee_csv_parser.add_argument("--folder", required=True, help="The Zotero collection (folder) name.")
    ieee_csv_parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    ieee_csv_parser.set_defaults(func=ieee_csv_command)

    # Add 'remove-attachments' subcommand
    remove_parser = subparsers.add_parser("remove-attachments", help="Remove all attachments from items in a folder.")
    remove_parser.add_argument("--folder", required=True, help="The Zotero collection (folder) name.")
    remove_parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    remove_parser.set_defaults(func=remove_attachments_command)

    # Add 'move' subcommand
    move_parser = subparsers.add_parser("move", help="Move a paper from one collection to another.")
    move_parser.add_argument("--id", required=True, help="The DOI or arXiv ID of the paper.")
    move_parser.add_argument("--from-col", required=True, help="The source collection name.")
    move_parser.add_argument("--to-col", required=True, help="The destiny collection name.")
    move_parser.set_defaults(func=move_command)

    # Add 'audit' subcommand
    audit_parser = subparsers.add_parser("audit", help="Audit a Zotero collection for completeness.")
    audit_parser.add_argument("--collection", required=True, help="The Zotero collection (folder) name to audit.")
    audit_parser.set_defaults(func=audit_command)

    # Add 'duplicates' subcommand
    duplicates_parser = subparsers.add_parser("duplicates", help="Find duplicate papers across specified collections.")
    duplicates_parser.add_argument("--collections", required=True, help="Comma-separated list of Zotero collection names.")
    duplicates_parser.set_defaults(func=duplicates_command)

    # Add 'graph' subcommand
    graph_parser = subparsers.add_parser("graph", help="Generate a citation graph in DOT format.")
    graph_parser.add_argument("--collections", required=True, help="Comma-separated list of Zotero collection names to build the graph from.")
    graph_parser.set_defaults(func=graph_command)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()
