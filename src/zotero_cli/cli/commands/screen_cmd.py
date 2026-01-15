import argparse
import sys
from rich.console import Console

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.cli.tui import TuiScreeningService

console = Console()

@CommandRegistry.register
class ScreenCommand(BaseCommand):
    name = "screen"
    help = "Interactive Screening Interface (TUI)"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--source", required=True, help="Source collection")
        parser.add_argument("--include", required=True, help="Target for inclusion")
        parser.add_argument("--exclude", required=True, help="Target for exclusion")
        parser.add_argument("--file", help="CSV file for bulk decisions (Headless mode)")
        parser.add_argument("--state", help="Local CSV file to track screening state")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        
        if args.file:
            self._handle_bulk(gateway, args)
        else:
            self._handle_tui(gateway, args)

    def _handle_tui(self, gateway, args):
        from zotero_cli.core.services.screening_state import ScreeningStateService
        state_manager = ScreeningStateService(args.state) if args.state else None
        
        tui = TuiScreeningService(gateway, state_manager)
        tui.run_screening_session(args.source, args.include, args.exclude)

    def _handle_bulk(self, gateway, args):
        service = ScreeningService(gateway)
        print(f"Processing bulk decisions from {args.file}...")
        
        import csv
        success_count = 0
        fail_count = 0
        
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = row.get('Key')
                    vote = row.get('Vote')
                    reason = row.get('Reason', '')
                    
                    if not key or not vote:
                        continue
                        
                    if service.record_decision(key, vote, "bulk", reason, args.source, args.include if vote == "INCLUDE" else args.exclude):
                        success_count += 1
                    else:
                        fail_count += 1
            print(f"Done. Success: {success_count}, Failed: {fail_count}")
        except Exception as e:
            print(f"Error processing CSV: {e}")

@CommandRegistry.register
class DecideCommand(BaseCommand):
    name = "decide"
    help = "Record a single decision (CLI mode)"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--key", required=True)
        parser.add_argument("--vote", required=True, choices=["INCLUDE", "EXCLUDE"])
        parser.add_argument("--code", required=True)
        parser.add_argument("--reason")
        parser.add_argument("--source")
        parser.add_argument("--target")
        parser.add_argument("--agent-led", action="store_true")
        parser.add_argument("--persona")
        parser.add_argument("--phase", default="title_abstract")

    def execute(self, args: argparse.Namespace):
        from zotero_cli.infra.factory import GatewayFactory
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))
        service = ScreeningService(gateway)
        
        agent = args.persona if args.agent_led else "human"
        
        success = service.record_decision(
            args.key, 
            args.vote, 
            agent, 
            f"[{args.code}] {args.reason or ''}",
            args.source,
            args.target,
            args.phase
        )
        
        if success:
            print(f"Successfully recorded decision for {args.key}")
        else:
            print(f"Failed to record decision for {args.key}")
            sys.exit(1)
