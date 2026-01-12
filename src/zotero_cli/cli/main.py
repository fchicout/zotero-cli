import argparse
import os
import sys
import re

from zotero_cli.infra.zotero_api import ZoteroAPIClient
from zotero_cli.infra.arxiv_lib import ArxivLibGateway
from zotero_cli.infra.bibtex_lib import BibtexLibGateway
from zotero_cli.infra.ris_lib import RisLibGateway
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
from zotero_cli.client import PaperImporterClient, CollectionNotFoundError
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.services.audit_service import CollectionAuditor # Import CollectionAuditor
from zotero_cli.core.services.duplicate_service import DuplicateFinder
from zotero_cli.infra.crossref_api import CrossRefAPIClient
from zotero_cli.infra.semantic_scholar_api import SemanticScholarAPIClient 
from zotero_cli.infra.unpaywall_api import UnpaywallAPIClient 
from zotero_cli.core.services.graph_service import CitationGraphService
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService 
from zotero_cli.core.services.tag_service import TagService
from zotero_cli.core.services.attachment_service import AttachmentService 
from zotero_cli.core.services.arxiv_query_parser import ArxivQueryParser
from zotero_cli.core.services.snapshot_service import SnapshotService
from zotero_cli.core.services.lookup_service import LookupService
from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.cli.tui import TuiScreeningService

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

def tag_command(args):
    """Handles the 'tag' subcommand."""
    gateway = get_zotero_gateway()
    service = TagService(gateway)

    if args.tag_action == 'list':
        tags = service.list_tags()
        print(f"Found {len(tags)} tags:")
        for tag in tags:
            print(f"  - {tag}")

    elif args.tag_action == 'rename':
        if not args.old or not args.new:
            print("Error: --old and --new arguments are required for rename.")
            sys.exit(1)
        count = service.rename_tag(args.old, args.new)
        print(f"Renamed tag '{args.old}' to '{args.new}' on {count} items.")

    elif args.tag_action == 'delete':
        if not args.tag:
            print("Error: --tag argument is required for delete.")
            sys.exit(1)
        count = service.delete_tag(args.tag)
        print(f"Deleted tag '{args.tag}' from {count} items.")

    elif args.tag_action in ['add', 'remove']:
        if not args.item or not args.tags:
            print("Error: --item and --tags arguments are required for add/remove.")
            sys.exit(1)
        
        item = gateway.get_item(args.item)
        if not item:
            print(f"Item '{args.item}' not found.")
            sys.exit(1)

        tags_list = [t.strip() for t in args.tags.split(',')]
        
        if args.tag_action == 'add':
            success = service.add_tags_to_item(item.key, item, tags_list)
            action = "added to"
        else:
            success = service.remove_tags_from_item(item.key, item, tags_list)
            action = "removed from"

        if success:
            print(f"Successfully {action} item '{args.item}'.")
        else:
            print(f"Failed to update tags for item '{args.item}'.")

def attach_pdf_command(args):
    """Handles the 'attach-pdf' subcommand."""
    zotero_gateway = get_zotero_gateway()
    
    # Providers
    crossref = CrossRefAPIClient()
    s2 = SemanticScholarAPIClient()
    unpaywall = UnpaywallAPIClient()
    aggregator = MetadataAggregatorService([s2, crossref, unpaywall])
    
    service = AttachmentService(zotero_gateway, aggregator)
    
    count = service.attach_pdfs_to_collection(args.collection)
    print(f"Attached {count} PDFs to items in '{args.collection}'.")

def empty_collection_command(args):
    """Handles the 'empty-collection' subcommand."""
    gateway = get_zotero_gateway()
    service = CollectionService(gateway)
    
    count = service.empty_collection(args.collection, args.parent, args.verbose)
    print(f"Deleted {count} items from collection '{args.collection}'.")

def search_arxiv_command(args):
    """Handles the 'search-arxiv' subcommand."""
    query_str = None
    if args.query:
        query_str = args.query
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                query_str = f.read().strip()
        except FileNotFoundError:
            print(f"Error: Query file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
    
    if not query_str:
        print("Error: No query provided. Use --query or --file.", file=sys.stderr)
        sys.exit(1)
        
    parser = ArxivQueryParser()
    params = parser.parse(query_str)
    
    if args.verbose:
        print(f"Parsed Parameters:")
        print(f"  Query: {params.query}")
        print(f"  Max Results: {params.max_results}")
        print(f"  Sort By: {params.sort_by}")
        print(f"  Sort Order: {params.sort_order}")
        
    gateway = ArxivLibGateway()
    results = gateway.search(
        query=params.query,
        limit=params.max_results,
        sort_by=params.sort_by,
        sort_order=params.sort_order
    )
    
    # We need to list or count. Since it's an iterator, we iterate.
    count = 0
    print("Executing search...")
    for item in results:
        count += 1
        print(f"{count}. {item.title} ({item.year})")
        
    print(f"\nTotal papers found: {count}")

def freeze_command(args):
    """Handles the 'freeze' subcommand."""
    gateway = get_zotero_gateway()
    service = SnapshotService(gateway)

    def cli_progress(current: int, total: int, message: str):
        if total > 0:
            percent = (current / total) * 100
            sys.stdout.write(f"\r[{percent:5.1f}%] {message:<60}")
        else:
            sys.stdout.write(f"\r[ ... ] {message:<60}")
        sys.stdout.flush()

    print(f"Starting snapshot of collection '{args.collection}'...")
    success = service.freeze_collection(args.collection, args.output, cli_progress)
    print("") # New line after progress bar

    if success:
        print(f"Successfully froze collection '{args.collection}' to '{args.output}'.")
    else:
        print(f"Failed to freeze collection. Check stderr for details.")
        sys.exit(1)

def lookup_command(args):
    """Handles the 'lookup' subcommand."""
    gateway = get_zotero_gateway()
    service = LookupService(gateway)
    
    keys = []
    if args.keys:
        keys = [k.strip() for k in args.keys.split(',')]
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                keys = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
            
    if not keys:
        print("Error: No keys provided. Use --keys or --file.", file=sys.stderr)
        sys.exit(1)
        
    fields = [f.strip() for f in args.fields.split(',')]
    
    output = service.lookup_items(keys, fields, args.format)
    print(output)

def decision_command(args):
    """Handles the 'decision' subcommand."""
    gateway = get_zotero_gateway()
    service = ScreeningService(gateway)
    
    success = service.record_decision(
        item_key=args.key,
        decision=args.vote,
        code=args.code,
        reason=args.reason,
        source_collection=args.source,
        target_collection=args.target,
        agent="zotero-cli-agent" if args.agent_led else "zotero-cli"
    )
    
    if success:
        print(f"Successfully recorded decision '{args.vote}' for item '{args.key}'.")
    else:
        sys.exit(1)

def screen_command(args):
    """Handles the 'screen' subcommand (TUI)."""
    try:
        gateway = get_zotero_gateway()
        service = ScreeningService(gateway)
        tui = TuiScreeningService(service)
        tui.run_screening_session(args.source, args.include, args.exclude)
    except KeyboardInterrupt:
        print("\nSession interrupted by user.")
        sys.exit(0)

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
    
    query_str = None
    if args.query:
        query_str = args.query
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                query_str = f.read().strip()
        except FileNotFoundError:
            print(f"Error: Query file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty(): # Check if stdin is being piped
        query_str = sys.stdin.read().strip()
    
    if not query_str:
        print("Error: No query provided. Use --query, --file, or pipe input.", file=sys.stderr)
        sys.exit(1)

    # Parse query if it looks like the structured DSL
    if ';' in query_str and ':' in query_str:
        parser = ArxivQueryParser()
        params = parser.parse(query_str)
        final_query = params.query
        limit = params.max_results
        sort_by = params.sort_by
        sort_order = params.sort_order
    else:
        final_query = query_str
        limit = args.limit
        sort_by = "relevance"
        sort_order = "descending"

    try:
        imported_count = client.import_from_query(
            final_query, args.folder, limit, args.verbose, sort_by, sort_order
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
    parser = argparse.ArgumentParser(description="Zotero CLI tool.")
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

    # Add 'tag' subcommand
    tag_parser = subparsers.add_parser("tag", help="Manage Zotero tags.")
    tag_subparsers = tag_parser.add_subparsers(dest="tag_action", help="Tag actions")

    # tag list
    tag_list_parser = tag_subparsers.add_parser("list", help="List all tags.")
    
    # tag rename
    tag_rename_parser = tag_subparsers.add_parser("rename", help="Rename a tag library-wide.")
    tag_rename_parser.add_argument("--old", required=True, help="Old tag name.")
    tag_rename_parser.add_argument("--new", required=True, help="New tag name.")

    # tag delete
    tag_delete_parser = tag_subparsers.add_parser("delete", help="Delete a tag library-wide.")
    tag_delete_parser.add_argument("--tag", required=True, help="Tag name to delete.")

    # tag add
    tag_add_parser = tag_subparsers.add_parser("add", help="Add tags to an item.")
    tag_add_parser.add_argument("--item", required=True, help="Item Key.")
    tag_add_parser.add_argument("--tags", required=True, help="Comma-separated tags.")

    # tag remove
    tag_remove_parser = tag_subparsers.add_parser("remove", help="Remove tags from an item.")
    tag_remove_parser.add_argument("--item", required=True, help="Item Key.")
    tag_remove_parser.add_argument("--tags", required=True, help="Comma-separated tags.")

    tag_parser.set_defaults(func=tag_command)

    # Add 'attach-pdf' subcommand
    attach_pdf_parser = subparsers.add_parser("attach-pdf", help="Find and attach PDFs to items in a collection.")
    attach_pdf_parser.add_argument("--collection", required=True, help="The Zotero collection name.")
    attach_pdf_parser.set_defaults(func=attach_pdf_command)

    # Add 'empty-collection' subcommand
    empty_col_parser = subparsers.add_parser("empty-collection", help="Remove all items from a collection.")
    empty_col_parser.add_argument("--collection", required=True, help="The Zotero collection name.")
    empty_col_parser.add_argument("--parent", help="The parent collection name (optional, for disambiguation).")
    empty_col_parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    empty_col_parser.set_defaults(func=empty_collection_command)

    # Add 'search-arxiv' subcommand
    search_arxiv_parser = subparsers.add_parser("search-arxiv", help="Search arXiv using complex query string.")
    search_group = search_arxiv_parser.add_mutually_exclusive_group(required=True)
    search_group.add_argument("--query", help="The structured query string.")
    search_group.add_argument("--file", help="Path to a file containing the query.")
    search_arxiv_parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    search_arxiv_parser.set_defaults(func=search_arxiv_command)

    # Add 'freeze' subcommand
    freeze_parser = subparsers.add_parser("freeze", help="Create a JSON snapshot of a collection for audit.")
    freeze_parser.add_argument("--collection", required=True, help="The Zotero collection name to freeze.")
    freeze_parser.add_argument("--output", required=True, help="Output JSON file path.")
    freeze_parser.set_defaults(func=freeze_command)

    # Add 'lookup' subcommand
    lookup_parser = subparsers.add_parser("lookup", help="Bulk fetch item metadata by key.")
    keys_group = lookup_parser.add_mutually_exclusive_group(required=True)
    keys_group.add_argument("--keys", help="Comma-separated list of Zotero Item Keys.")
    keys_group.add_argument("--file", help="File containing list of keys (one per line).")
    
    lookup_parser.add_argument("--fields", default="key,arxiv_id,title,date,url", help="Comma-separated list of fields to include. Default: key,arxiv_id,title,date,url")
    lookup_parser.add_argument("--format", default="table", choices=["table", "csv", "json"], help="Output format. Default: table.")
    lookup_parser.set_defaults(func=lookup_command)

    # Add 'decision' subcommand
    decision_parser = subparsers.add_parser("decision", help="Record a screening decision for an item.")
    decision_parser.add_argument("--key", required=True, help="Zotero Item Key.")
    decision_parser.add_argument("--vote", required=True, choices=["INCLUDE", "EXCLUDE"], help="The decision (INCLUDE/EXCLUDE).")
    decision_parser.add_argument("--code", required=True, help="Criterion code (e.g., IC1, EC4).")
    decision_parser.add_argument("--reason", help="Optional reason text.")
    decision_parser.add_argument("--source", help="Optional source collection name (to move from).")
    decision_parser.add_argument("--target", help="Optional target collection name (to move to).")
    decision_parser.add_argument("--agent-led", action="store_true", help="Flag if decision was made by an agent.")
    decision_parser.set_defaults(func=decision_command)

    # Add 'screen' subcommand
    screen_parser = subparsers.add_parser("screen", help="Interactive TUI for screening papers.")
    screen_parser.add_argument("--source", required=True, help="Source collection (e.g., 'raw_arXiv').")
    screen_parser.add_argument("--include", required=True, help="Target collection for inclusions.")
    screen_parser.add_argument("--exclude", required=True, help="Target collection for exclusions.")
    screen_parser.set_defaults(func=screen_command)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()
