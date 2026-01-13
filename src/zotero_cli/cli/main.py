import argparse
import os
import sys
import re
from typing import Optional

from zotero_cli.infra.zotero_api import ZoteroAPIClient
from zotero_cli.infra.arxiv_lib import ArxivLibGateway
from zotero_cli.infra.bibtex_lib import BibtexLibGateway
from zotero_cli.infra.ris_lib import RisLibGateway
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
from zotero_cli.client import PaperImporterClient, CollectionNotFoundError
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.services.audit_service import CollectionAuditor
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
from zotero_cli.core.services.report_service import ReportService
from zotero_cli.core.services.migration_service import MigrationService
from zotero_cli.cli.tui import TuiScreeningService

# --- Infrastructure Helpers ---

# --- Infrastructure Helpers ---

FORCE_USER = False

def get_zotero_gateway(require_group: bool = True):
    """
    Helper to get Zotero client from environment variables.
    Supports both Group and User libraries.
    """
    api_key = os.environ.get("ZOTERO_API_KEY")
    if not api_key:
        print("Error: ZOTERO_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # Determine Library Context
    group_url = os.environ.get("ZOTERO_TARGET_GROUP")
    user_id = os.environ.get("ZOTERO_USER_ID")
    
    # Logic:
    # 1. If FORCE_USER is True (set via CLI flag), skip Group check and try User ID.
    # 2. If TARGET_GROUP is set, use it (Group Mode).
    # 3. If TARGET_GROUP is NOT set, but USER_ID is set, use User Mode.
    # 4. If neither, check require_group.

    if group_url and not FORCE_USER:
        match = re.search(r'/groups/(\d+)', group_url)
        library_id = match.group(1) if match else None
        if not library_id:
             print(f"Error: Could not extract Group ID from URL: {group_url}", file=sys.stderr)
             sys.exit(1)
        library_type = 'group'
    elif user_id:
        library_id = user_id
        library_type = 'user'
    else:
        # Fallback/Error state
        if require_group:
             print("Error: Neither ZOTERO_TARGET_GROUP nor ZOTERO_USER_ID is set.", file=sys.stderr)
             print("Please set one to define the target library.", file=sys.stderr)
             sys.exit(1)
        else:
            library_id = "0"
            library_type = 'user'

    return ZoteroAPIClient(api_key, library_id, library_type)

def get_common_clients():
    zotero_gateway = get_zotero_gateway()
    arxiv_gateway = ArxivLibGateway()
    bibtex_gateway = BibtexLibGateway()
    ris_gateway = RisLibGateway()
    springer_csv_gateway = SpringerCsvLibGateway()
    ieee_csv_gateway = IeeeCsvLibGateway()
    return PaperImporterClient(zotero_gateway, arxiv_gateway, bibtex_gateway, ris_gateway, springer_csv_gateway, ieee_csv_gateway)

# --- Handlers (Adapters for New Command Structure) ---

# 1. SCREEN
def handle_screen_run(args):
    try:
        gateway = get_zotero_gateway()
        service = ScreeningService(gateway)
        tui = TuiScreeningService(service)
        tui.run_screening_session(args.source, args.include, args.exclude)
    except KeyboardInterrupt:
        print("\nSession interrupted by user.")
        sys.exit(0)

def handle_screen_record(args):
    gateway = get_zotero_gateway()
    service = ScreeningService(gateway)
    success = service.record_decision(
        item_key=args.key,
        decision=args.vote,
        code=args.code,
        reason=args.reason,
        source_collection=args.source,
        target_collection=args.target,
        agent="zotero-cli-agent" if args.agent_led else "zotero-cli",
        persona=args.persona if args.persona else "unknown",
        phase=args.phase
    )
    if success:
        print(f"Successfully recorded decision '{args.vote}' for item '{args.key}'.")
    else:
        sys.exit(1)

# 2. IMPORT
def handle_import_file(args):
    client = get_common_clients()
    file_path = args.file
    folder = args.collection
    verbose = args.verbose
    
    # Auto-detect format
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.bib':
            count = client.import_from_bibtex(file_path, folder, verbose)
        elif ext == '.ris':
            count = client.import_from_ris(file_path, folder, verbose)
        elif ext == '.csv':
            # Basic heuristic for CSV type
            with open(file_path, 'r', encoding='utf-8') as f:
                header = f.readline()
                if 'Item Title' in header and 'Publication Title' in header: # Springer heuristic
                     count = client.import_from_springer_csv(file_path, folder, verbose)
                elif 'Document Title' in header: # IEEE heuristic
                     count = client.import_from_ieee_csv(file_path, folder, verbose)
                else:
                    print("Error: Unknown CSV format. Only Springer and IEEE Xplore CSVs are supported.", file=sys.stderr)
                    sys.exit(1)
        else:
            print(f"Error: Unsupported file extension '{ext}'.", file=sys.stderr)
            sys.exit(1)
            
        print(f"Successfully imported {count} papers from '{file_path}' to '{folder}'.")
    except Exception as e:
        print(f"Import failed: {e}", file=sys.stderr)
        sys.exit(1)

def handle_import_arxiv(args):
    client = get_common_clients()
    query_str = args.query
    if args.file:
        try:
            with open(args.file, 'r') as f:
                query_str = f.read().strip()
        except FileNotFoundError:
            print(f"Error: Query file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
    
    if not query_str:
        print("Error: No query provided.", file=sys.stderr)
        sys.exit(1)

    # DSL Parsing logic
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
        count = client.import_from_query(final_query, args.collection, limit, args.verbose, sort_by, sort_order)
        print(f"Successfully imported {count} papers to '{args.collection}'.")
    except Exception as e:
        print(f"ArXiv import failed: {e}", file=sys.stderr)
        sys.exit(1)

def handle_import_manual(args):
    client = get_common_clients()
    try:
        success = client.add_paper(args.arxiv_id, args.abstract, args.title, args.collection)
        if success:
            print(f"Successfully added '{args.title}' to '{args.collection}'.")
        else:
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

# 3. LIST
def handle_list_collections(args):
    gateway = get_zotero_gateway()
    collections = gateway.get_all_collections()
    if collections:
        print(f"Found {len(collections)} collections:")
        for col in collections:
            num_items = col.get('meta', {}).get('numItems', '?')
            print(f"  - {col['data']['name']} (Key: {col['key']}, Items: {num_items})")
    else:
        print("No collections found.")

def handle_list_groups(args):
    user_id = os.environ.get("ZOTERO_USER_ID")
    if not user_id:
        print("Error: ZOTERO_USER_ID env var required.", file=sys.stderr)
        sys.exit(1)
    
    # Force user mode for this command
    gateway = ZoteroAPIClient(os.environ.get("ZOTERO_API_KEY"), user_id, 'user')
    groups = gateway.get_user_groups(user_id)
    
    if groups:
        print(f"Found {len(groups)} groups for User {user_id}:")
        from rich.console import Console
        from rich.table import Table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Access")
        table.add_column("URL")
        for g in groups:
            data = g.get('data', {})
            gid = str(data.get('id', 'N/A'))
            name = data.get('name', 'N/A')
            access = f"{data.get('type')} ({data.get('libraryEditing')})"
            url = f"https://www.zotero.org/groups/{gid}"
            table.add_row(gid, name, access, url)
        Console().print(table)
    else:
        print("No groups found.")

def handle_list_items(args):
    gateway = get_zotero_gateway()
    
    # Try direct name match
    col_id = gateway.get_collection_id_by_name(args.collection)
    
    if not col_id:
        # Try case-insensitive partial match
        cols = gateway.get_all_collections()
        for c in cols:
            cname = c.get('data', {}).get('name', '')
            if args.collection.lower() in cname.lower():
                col_id = c['key']
                print(f"Matched collection '{cname}' (Key: {col_id})")
                break
    
    if not col_id:
        col_id = args.collection # Assume it's a key if no name match found
    
    items = gateway.get_items_in_collection(col_id)
    
    from rich.console import Console
    from rich.table import Table
    console = Console()
    
    table = Table(title=f"Items in {args.collection}")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Key", style="dim")
    table.add_column("Type", style="yellow")
    
    count = 0
    paper_count = 0
    
    for item in items:
        # Filter out attachments and notes for the high-level list
        if item.item_type in ['attachment', 'note']:
            continue
            
        paper_count += 1
        table.add_row(str(paper_count), item.title[:80], item.key, item.item_type)
        
    console.print(table)
    console.print(f"\n[dim]Showing {paper_count} papers (attachments/notes hidden). Use 'zotero-cli inspect --key <KEY>' for details.[/dim]")

# 4. REPORT
def handle_report_prisma(args):
    gateway = get_zotero_gateway()
    service = ReportService(gateway)
    report = service.generate_prisma_report(args.collection)
    if not report:
        print(f"Error: Collection '{args.collection}' not found.")
        sys.exit(1)
        
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
    
    summary = f"""
    [bold blue]Collection:[/bold blue] {report.collection_name}
    [bold blue]Total Items:[/bold blue] {report.total_items}
    [bold blue]Screened:[/bold blue] {report.screened_items} ({ (report.screened_items/report.total_items*100) if report.total_items > 0 else 0:.1f}%)
    [bold green]Accepted:[/bold green] {report.accepted_items}
    [bold red]Rejected:[/bold red] {report.rejected_items}
    """
    console.print(Panel(summary, title="PRISMA Screening Summary", expand=False))
    
    if report.rejections_by_code:
        table = Table(title="Rejection Reasons")
        table.add_column("Code", style="cyan")
        table.add_column("Count", justify="right", style="magenta")
        table.add_column("%", justify="right", style="green")
        for code, count in sorted(report.rejections_by_code.items()):
            percent = (count / report.rejected_items * 100) if report.rejected_items > 0 else 0
            table.add_row(code, str(count), f"{percent:.1f}%")
        console.print(table)

    if args.output_chart:
        mermaid_code = service.generate_mermaid_prisma(report)
        if service.render_diagram(mermaid_code, args.output_chart):
            console.print(f"\n[bold green]✓ Diagram saved to {args.output_chart}[/bold green]")
        else:
            console.print(f"\n[bold red]✗ Failed to render diagram.[/bold red]")

def handle_report_snapshot(args):
    gateway = get_zotero_gateway()
    service = SnapshotService(gateway)
    
    def cli_progress(current, total, msg):
        sys.stdout.write(f"\r[{(current/total)*100:5.1f}%] {msg:<60}")
        sys.stdout.flush()

    print(f"Snapshotting '{args.collection}'...")
    success = service.freeze_collection(args.collection, args.output, cli_progress)
    print("")
    if success:
        print(f"Snapshot saved to '{args.output}'.")
    else:
        sys.exit(1)

# 5. MANAGE
def handle_manage_tags(args):
    gateway = get_zotero_gateway()
    service = TagService(gateway)
    
    if args.action == 'list':
        tags = service.list_tags()
        print(f"Found {len(tags)} tags.")
        for t in tags: print(f"- {t}")
    elif args.action == 'rename':
        count = service.rename_tag(args.old, args.new)
        print(f"Renamed '{args.old}' to '{args.new}' on {count} items.")
    elif args.action == 'delete':
        count = service.delete_tag(args.tag)
        print(f"Deleted tag '{args.tag}' from {count} items.")
    elif args.action == 'add':
        item = gateway.get_item(args.item)
        if item and service.add_tags_to_item(item.key, item, [t.strip() for t in args.tags.split(',')]):
            print(f"Tags added to '{args.item}'.")
    elif args.action == 'remove':
        item = gateway.get_item(args.item)
        if item and service.remove_tags_from_item(item.key, item, [t.strip() for t in args.tags.split(',')]):
            print(f"Tags removed from '{args.item}'.")

def handle_manage_pdfs(args):
    gateway = get_zotero_gateway()
    if args.action == 'fetch':
        # Instantiating aggregators...
        aggregator = MetadataAggregatorService([SemanticScholarAPIClient(), CrossRefAPIClient(), UnpaywallAPIClient()])
        service = AttachmentService(gateway, aggregator)
        count = service.attach_pdfs_to_collection(args.collection)
        print(f"Attached {count} PDFs.")
    elif args.action == 'strip':
        client = get_common_clients()
        count = client.remove_attachments_from_folder(args.collection, args.verbose)
        print(f"Removed {count} attachments.")

def handle_manage_duplicates(args):
    gateway = get_zotero_gateway()
    finder = DuplicateFinder(gateway)
    groups = finder.find_duplicates([c.strip() for c in args.collections.split(',')])
    if groups:
        print(f"Found {len(groups)} duplicates.")
        for i, g in enumerate(groups):
            print(f"Group {i+1}: {g.identifier_key}")
            for item in g.items:
                print(f"  - {item.title} (Key: {item.key})")
    else:
        print("No duplicates found.")

def handle_manage_move(args):
    gateway = get_zotero_gateway()
    service = CollectionService(gateway)
    if service.move_item(args.source, args.target, args.item_id):
        print(f"Moved item {args.item_id}.")
    else:
        print("Move failed.")

def handle_manage_clean(args):
    gateway = get_zotero_gateway()
    service = CollectionService(gateway)
    count = service.empty_collection(args.collection, args.parent, args.verbose)
    print(f"Deleted {count} items.")

def handle_manage_migrate(args):
    gateway = get_zotero_gateway()
    service = MigrationService(gateway)
    stats = service.migrate_collection_notes(args.collection, args.dry_run)
    if "error" in stats:
        print("Error: Collection not found.")
        sys.exit(1)
    print(f"Processed: {stats['processed']}, Migrated: {stats['migrated']}, Failed: {stats['failed']}")

# 6. ANALYZE
def handle_analyze_audit(args):
    gateway = get_zotero_gateway()
    auditor = CollectionAuditor(gateway)
    report = auditor.audit_collection(args.collection)
    if report:
        print(f"Audit Report for '{args.collection}':")
        print(f"  Missing IDs: {len(report.items_missing_id)}")
        print(f"  Missing PDFs: {len(report.items_missing_pdf)}")
    else:
        sys.exit(1)

def handle_analyze_lookup(args):
    gateway = get_zotero_gateway()
    service = LookupService(gateway)
    keys = []
    if args.keys: keys = [k.strip() for k in args.keys.split(',')]
    elif args.file:
        with open(args.file) as f: keys = [l.strip() for l in f if l.strip()]
    
    print(service.lookup_items(keys, [f.strip() for f in args.fields.split(',')], args.format))

def handle_analyze_graph(args):
    gateway = get_zotero_gateway()
    aggregator = MetadataAggregatorService([SemanticScholarAPIClient(), CrossRefAPIClient(), UnpaywallAPIClient()])
    service = CitationGraphService(gateway, aggregator)
    print(service.build_graph([c.strip() for c in args.collections.split(',')]))

def handle_find_arxiv(args):
    # Re-using import logic but just printing
    query_str = args.query
    if not query_str and args.file:
        with open(args.file) as f: query_str = f.read().strip()
    
    parser = ArxivQueryParser()
    params = parser.parse(query_str)
    gateway = ArxivLibGateway()
    results = gateway.search(params.query, params.max_results, params.sort_by, params.sort_order)
    
    i = 0
    for item in results:
        i+=1
        print(f"{i}. {item.title} ({item.year})")
    print(f"Found {i} papers.")


def handle_info(args):
    """Display diagnostic information."""
    from rich.table import Table
    from rich.console import Console
    from rich import box
    console = Console()
    
    api_key = os.getenv('ZOTERO_API_KEY')
    target_group = os.getenv('ZOTERO_TARGET_GROUP')
    user_id = os.getenv('ZOTERO_USER_ID')
    
    table = Table(title="Zotero CLI Configuration", box=box.ROUNDED)
    table.add_column("Variable", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="yellow")
    
    table.add_row("API Key", f"{api_key[:4]}...{api_key[-4:]}" if api_key else "None", "OK" if api_key else "MISSING")
    table.add_row("Target Group", target_group or "None", "SET" if target_group else "UNSET")
    table.add_row("User ID", user_id or "None", "SET" if user_id else "UNSET")
    
    console.print(table)
    
    try:
        gw = get_zotero_gateway(require_group=False)
        context_table = Table(title="Active Context", box=box.MINIMAL_DOUBLE_HEAD)
        context_table.add_column("Property")
        context_table.add_column("Value")
        context_table.add_row("Library Type", gw.http.library_type.upper())
        context_table.add_row("Library ID", gw.http.library_id)
        context_table.add_row("API Prefix", gw.http.api_prefix)
        console.print(context_table)
    except Exception as e:
        console.print(f"[bold red]Error deriving context:[/bold red] {e}")

def handle_inspect_item(args):
    """Show detailed information for a specific item."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.json import JSON
    import json
    console = Console()
    
    gateway = get_zotero_gateway()
    item = gateway.get_item(args.key)
    
    if not item:
        console.print(f"[bold red]Item '{args.key}' not found.[/bold red]")
        sys.exit(1)
        
    # Metadata Panel
    meta_text = f"""
    [bold]Title:[/bold] {item.title}
    [bold]Type:[/bold] {item.item_type}
    [bold]Year:[/bold] {item.year}
    [bold]Authors:[/bold] {', '.join(item.creators)}
    [bold]DOI:[/bold] {item.doi}
    [bold]URL:[/bold] {item.url}
    """
    console.print(Panel(meta_text, title=f"Item: {item.key}", expand=False))
    
    # Abstract
    if item.abstract:
        console.print(Panel(item.abstract, title="Abstract", border_style="blue"))
        
    # Raw JSON
    if args.raw:
        # We need to re-fetch raw or expose raw_data in ZoteroItem
        # ZoteroItem stores raw data in a way, but let's just dump the object dict for now
        # Or better, fetch raw again if needed, or expose it.
        # ZoteroItem.from_raw_zotero_item doesn't store the full raw dict?
        # Let's check ZoteroItem definition.
        pass # Placeholder for raw
        
    # Children (Notes/Attachments)
    children = gateway.get_item_children(args.key)
    if children:
        console.print(f"\n[bold]Children ({len(children)}):[/bold]")
        for child in children:
            c_data = child.get('data', {})
            c_type = c_data.get('itemType')
            c_title = c_data.get('title') or c_data.get('note', '')[:50]
            console.print(f" - [{c_type}] {c_title} (Key: {child['key']})")

# --- Main Router ---

def main():
    parser = argparse.ArgumentParser(description="Zotero CLI - The Systematic Review Engine")
    parser.add_argument("--user", action="store_true", help="Force Personal Library mode")
    subparsers = parser.add_subparsers(dest='command', help='Primary Commands')
    
    # --- INFO ---
    parser_info = subparsers.add_parser('info', help='Display environment and configuration')
    parser_info.set_defaults(func=handle_info)
    
    # --- INSPECT ---
    inspect_parser = subparsers.add_parser('inspect', help='Inspect item details')
    inspect_parser.add_argument('--key', required=True, help='Zotero Item Key')
    inspect_parser.add_argument('--raw', action='store_true', help='Show raw JSON')
    inspect_parser.set_defaults(func=handle_inspect_item)
    
    # --- SCREEN ---
    screen_parser = subparsers.add_parser("screen", help="Interactive Screening Interface (TUI)")
    screen_parser.add_argument("--source", required=True, help="Source collection")
    screen_parser.add_argument("--include", required=True, help="Target for inclusion")
    screen_parser.add_argument("--exclude", required=True, help="Target for exclusion")
    screen_parser.set_defaults(func=handle_screen_run)

    # 2. DECIDE (CLI Mode)
    decide_parser = subparsers.add_parser("decide", help="Record a decision (CLI mode)")
    decide_parser.add_argument("--key", required=True)
    decide_parser.add_argument("--vote", required=True, choices=["INCLUDE", "EXCLUDE"])
    decide_parser.add_argument("--code", required=True)
    decide_parser.add_argument("--reason")
    decide_parser.add_argument("--source")
    decide_parser.add_argument("--target")
    decide_parser.add_argument("--agent-led", action="store_true")
    decide_parser.add_argument("--persona")
    decide_parser.add_argument("--phase", default="title_abstract")
    decide_parser.set_defaults(func=handle_screen_record)

    # 3. IMPORT
    import_parser = subparsers.add_parser("import", help="Ingest papers")
    import_sub = import_parser.add_subparsers(dest="import_type", required=True)

    # import file
    file_parser = import_sub.add_parser("file", help="Import .bib, .ris, .csv")
    file_parser.add_argument("file", help="Path to file")
    file_parser.add_argument("--collection", required=True)
    file_parser.add_argument("--verbose", action="store_true")
    file_parser.set_defaults(func=handle_import_file)

    # import arxiv
    arxiv_parser = import_sub.add_parser("arxiv", help="Import from arXiv query")
    group = arxiv_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", help="Query string")
    group.add_argument("--file", help="Query file")
    arxiv_parser.add_argument("--collection", required=True)
    arxiv_parser.add_argument("--limit", type=int, default=100)
    arxiv_parser.add_argument("--verbose", action="store_true")
    arxiv_parser.set_defaults(func=handle_import_arxiv)

    # import manual
    manual_parser = import_sub.add_parser("manual", help="Manually add a paper")
    manual_parser.add_argument("--title", required=True)
    manual_parser.add_argument("--arxiv-id", required=True)
    manual_parser.add_argument("--abstract", required=True)
    manual_parser.add_argument("--collection", required=True)
    manual_parser.set_defaults(func=handle_import_manual)

    # 4. LIST
    list_parser = subparsers.add_parser("list", help="Discovery")
    list_sub = list_parser.add_subparsers(dest="list_type", required=True)
    
    list_sub.add_parser("collections", help="List collections").set_defaults(func=handle_list_collections)
    list_sub.add_parser("groups", help="List user groups").set_defaults(func=handle_list_groups)
    
    li_parser = list_sub.add_parser("items", help="List items in collection")
    li_parser.add_argument("--collection", required=True)
    li_parser.set_defaults(func=handle_list_items)

    # 5. REPORT
    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_sub = report_parser.add_subparsers(dest="report_type", required=True)
    
    prisma_parser = report_sub.add_parser("prisma", help="PRISMA Statistics")
    prisma_parser.add_argument("--collection", required=True)
    prisma_parser.add_argument("--output-chart")
    prisma_parser.add_argument("--verbose", action="store_true")
    prisma_parser.set_defaults(func=handle_report_prisma)

    snap_parser = report_sub.add_parser("snapshot", help="JSON Audit Snapshot")
    snap_parser.add_argument("--collection", required=True)
    snap_parser.add_argument("--output", required=True)
    snap_parser.set_defaults(func=handle_report_snapshot)

    # 6. MANAGE
    manage_parser = subparsers.add_parser("manage", help="Library Maintenance")
    manage_sub = manage_parser.add_subparsers(dest="manage_type", required=True)

    # manage tags
    tag_parser = manage_sub.add_parser("tags", help="Tag operations")
    tag_parser.add_argument("action", choices=["list", "rename", "delete", "add", "remove"])
    tag_parser.add_argument("--tag")
    tag_parser.add_argument("--old")
    tag_parser.add_argument("--new")
    tag_parser.add_argument("--item")
    tag_parser.add_argument("--tags")
    tag_parser.set_defaults(func=handle_manage_tags)

    # manage pdfs
    pdf_parser = manage_sub.add_parser("pdfs", help="PDF operations")
    pdf_parser.add_argument("action", choices=["fetch", "strip"])
    pdf_parser.add_argument("--collection", required=True)
    pdf_parser.add_argument("--verbose", action="store_true")
    pdf_parser.set_defaults(func=handle_manage_pdfs)

    # manage duplicates
    dup_parser = manage_sub.add_parser("duplicates", help="Find duplicates")
    dup_parser.add_argument("--collections", required=True)
    dup_parser.set_defaults(func=handle_manage_duplicates)

    # manage move
    move_parser = manage_sub.add_parser("move", help="Move item")
    move_parser.add_argument("--item-id", required=True)
    move_parser.add_argument("--source", required=True)
    move_parser.add_argument("--target", required=True)
    move_parser.set_defaults(func=handle_manage_move)

    # manage clean
    clean_parser = manage_sub.add_parser("clean", help="Empty a collection")
    clean_parser.add_argument("--collection", required=True)
    clean_parser.add_argument("--parent")
    clean_parser.add_argument("--verbose", action="store_true")
    clean_parser.set_defaults(func=handle_manage_clean)

    # manage migrate
    mig_parser = manage_sub.add_parser("migrate", help="Migrate audit notes")
    mig_parser.add_argument("--collection", required=True)
    mig_parser.add_argument("--dry-run", action="store_true")
    mig_parser.set_defaults(func=handle_manage_migrate)

    # 7. ANALYZE
    analyze_parser = subparsers.add_parser("analyze", help="Analysis & Visualization")
    analyze_sub = analyze_parser.add_subparsers(dest="analyze_type", required=True)

    # analyze audit
    audit_parser = analyze_sub.add_parser("audit", help="Check for missing data")
    audit_parser.add_argument("--collection", required=True)
    audit_parser.set_defaults(func=handle_analyze_audit)

    # analyze lookup
    lookup_parser = analyze_sub.add_parser("lookup", help="Bulk metadata fetch")
    lookup_parser.add_argument("--keys")
    lookup_parser.add_argument("--file")
    lookup_parser.add_argument("--fields", default="key,arxiv_id,title,date,url")
    lookup_parser.add_argument("--format", default="table")
    lookup_parser.set_defaults(func=handle_analyze_lookup)

    # analyze graph
    graph_parser = analyze_sub.add_parser("graph", help="Citation Graph")
    graph_parser.add_argument("--collections", required=True)
    graph_parser.set_defaults(func=handle_analyze_graph)

    # 8. FIND
    find_parser = subparsers.add_parser("find", help="Discovery")
    find_sub = find_parser.add_subparsers(dest="find_source", required=True)
    
    arxiv_find = find_sub.add_parser("arxiv", help="Search arXiv")
    group_f = arxiv_find.add_mutually_exclusive_group(required=True)
    group_f.add_argument("--query")
    group_f.add_argument("--file")
    arxiv_find.add_argument("--verbose", action="store_true")
    arxiv_find.set_defaults(func=handle_find_arxiv)

    args = parser.parse_args()
    
    global FORCE_USER
    FORCE_USER = args.user

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()