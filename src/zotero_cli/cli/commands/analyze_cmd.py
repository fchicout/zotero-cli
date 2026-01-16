import argparse
import json

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.audit_service import CollectionAuditor
from zotero_cli.core.services.graph_service import CitationGraphService
from zotero_cli.core.services.lookup_service import LookupService

console = Console()

@CommandRegistry.register
class AnalyzeCommand(BaseCommand):
    name = "analyze"
    help = "Analysis & Visualization (audit, lookup, graph, shift)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="analyze_type", required=True)

        # Audit
        audit_p = sub.add_parser("audit", help="Check for missing data")
        audit_p.add_argument("--collection", required=True)

        # Lookup
        lookup_p = sub.add_parser("lookup", help="Bulk metadata fetch")
        lookup_p.add_argument("--keys")
        lookup_p.add_argument("--file")
        lookup_p.add_argument("--fields", default="key,arxiv_id,title,date,url")
        lookup_p.add_argument("--format", default="table")

        # Graph
        graph_p = sub.add_parser("graph", help="Citation Graph")
        graph_p.add_argument("--collections", required=True)

        # Shift
        shift_p = sub.add_parser("shift", help="Detect items that moved between collections")
        shift_p.add_argument("--old", required=True, help="Old Snapshot JSON")
        shift_p.add_argument("--new", required=True, help="New Snapshot JSON")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))

        if args.analyze_type == "audit":
            self._handle_audit(gateway, args)
        elif args.analyze_type == "lookup":
            self._handle_lookup(gateway, args)
        elif args.analyze_type == "graph":
            self._handle_graph(gateway, args)
        elif args.analyze_type == "shift":
            self._handle_shift(gateway, args)

    def _handle_shift(self, gateway, args):
        service = CollectionAuditor(gateway)
        with open(args.old, 'r') as f:
            old_data = json.load(f)
            snap_old = old_data.get('items', old_data) if isinstance(old_data, dict) else old_data
        with open(args.new, 'r') as f:
            new_data = json.load(f)
            snap_new = new_data.get('items', new_data) if isinstance(new_data, dict) else new_data

        shifts = service.detect_shifts(snap_old, snap_new)

        if not shifts:
            console.print("[bold green]No shifts detected. State is stable.[/bold green]")
            return

        table = Table(title="Collection Shifts (Drift Detection)")
        table.add_column("Key")
        table.add_column("Title")
        table.add_column("From", style="red")
        table.add_column("To", style="green")

        for s in shifts:
            table.add_row(
                s['key'],
                s['title'][:50],
                ", ".join(s['from']),
                ", ".join(s['to'])
            )
        console.print(table)

    def _handle_audit(self, gateway, args):
        service = CollectionAuditor(gateway)
        report = service.audit_collection(args.collection)

        if not report:
            console.print(f"[bold red]Audit failed for collection: {args.collection}[/bold red]")
            return

        console.print(f"[bold]Audit Report for {args.collection}:[/bold]")
        console.print(f"  Missing IDs: {len(report.items_missing_id)}")
        console.print(f"  Missing PDFs: {len(report.items_missing_pdf)}")

    def _handle_lookup(self, gateway, args):
        service = LookupService(gateway)
        keys = args.keys.split(',') if args.keys else []
        if args.file:
            with open(args.file) as f:
                keys.extend([line.strip() for line in f if line.strip()])

        fields = args.fields.split(',')
        result = service.lookup_items(keys, fields, args.format)
        print(result)

    def _handle_graph(self, gateway, args):
        from zotero_cli.infra.factory import GatewayFactory
        meta_service = GatewayFactory.get_metadata_aggregator()
        service = CitationGraphService(gateway, meta_service)
        col_ids = [c.strip() for c in args.collections.split(',')]
        dot = service.build_graph(col_ids)
        print(dot)
