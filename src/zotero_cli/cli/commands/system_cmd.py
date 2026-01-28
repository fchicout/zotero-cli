import argparse
import os
import sys
from typing import Any

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.commands.list_cmd import ListCommand
from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.strategies import (
    BibtexImportStrategy,
    CanonicalCsvImportStrategy,
    IeeeCsvImportStrategy,
    RisImportStrategy,
    SpringerCsvImportStrategy,
)
from zotero_cli.infra.bibtex_lib import BibtexLibGateway
from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
from zotero_cli.infra.ris_lib import RisLibGateway
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway


class InfoCommand(BaseCommand):
    name = "info"
    help = "Display environment and configuration"

    def register_args(self, parser: argparse.ArgumentParser):
        pass  # No extra args for info

    def execute(self, args: argparse.Namespace):
        from zotero_cli.core.config import get_config, get_config_path

        config = get_config(args.config)

        print("--- Zotero CLI Info ---")
        print(f"Config Path: {get_config_path() or 'None (using defaults/env)'}")
        print(f"Library ID:  {config.library_id}")
        print(f"Library Type: {config.library_type}")
        print(f"API Key:     {'********' if config.api_key else 'NOT SET'}")
        if config.target_group_url:
            print(f"Group URL:   {config.target_group_url}")


@CommandRegistry.register
class SystemCommand(BaseCommand):
    name = "system"
    help = "System maintenance & information"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # Info
        sub.add_parser("info", help=InfoCommand.help)

        # Groups
        sub.add_parser("groups", help="List user groups and IDs")

        # Backup
        backup_p = sub.add_parser("backup", help="Create a full system backup (.zaf)")
        backup_p.add_argument("--output", required=True, help="Output file path (e.g., backup.zaf)")

        # Restore (Placeholder for now, implemented logic pending)
        restore_p = sub.add_parser("restore", help="Restore from a .zaf backup")
        restore_p.add_argument("--file", required=True, help="Input .zaf file")
        restore_p.add_argument("--dry-run", action="store_true", help="Simulate restore")

        # Normalize CSV
        norm_p = sub.add_parser(
            "normalize", help="Convert external CSV (IEEE, Springer) to Canonical format"
        )
        norm_p.add_argument("file", help="Input CSV file")
        norm_p.add_argument("--output", required=True, help="Output Canonical CSV path")

        # Switch Context
        switch_p = sub.add_parser("switch", help="Switch active group context")
        switch_p.add_argument("query", help="Group ID or Name (partial match)")

    def execute(self, args: argparse.Namespace):
        if args.verb == "info":
            InfoCommand().execute(args)
        elif args.verb == "groups":
            args.list_type = "groups"
            ListCommand().execute(args)
        elif args.verb == "backup":
            self._handle_backup(args)
        elif args.verb == "restore":
            print("Restore functionality is pending implementation.")
        elif args.verb == "normalize":
            self._handle_normalize(args)
        elif args.verb == "switch":
            self._handle_switch(args)

    def _handle_switch(self, args):
        from rich.prompt import Confirm
        from zotero_cli.core.config import ConfigManager, get_config
        from zotero_cli.infra.factory import GatewayFactory

        config = get_config()
        if not config.user_id:
            print("Error: ZOTERO_USER_ID not configured. Cannot fetch user groups.")
            return

        gateway = GatewayFactory.get_zotero_gateway(force_user=True)
        groups = gateway.get_user_groups(config.user_id)
        
        query = args.query.lower()
        matches = []
        
        for g in groups:
            gid = str(g.get("id"))
            name = g.get("data", {}).get("name", "").lower()
            if query == gid or query in name:
                matches.append(g)
        
        if not matches:
            print(f"No groups found matching '{args.query}'.")
            return
        
        if len(matches) > 1:
            print(f"Multiple groups found matching '{args.query}':")
            for g in matches:
                print(f" - {g.get('data', {}).get('name')} ({g.get('id')})")
            print("Please be more specific.")
            return
        
        target = matches[0]
        target_name = target.get("data", {}).get("name")
        target_id = str(target.get("id"))
        
        if Confirm.ask(f"Switch context to group '{target_name}' ({target_id})?"):
            try:
                manager = ConfigManager()
                manager.save_group_context(target_id)
                print(f"[green]Switched context to group: {target_name} ({target_id})[/green]")
            except Exception as e:
                print(f"[red]Failed to save configuration: {e}[/red]")

    def _handle_normalize(self, args):
        ext = os.path.splitext(args.file)[1].lower()
        strategy: Any = None
        gateway: Any = None

        if ext == ".bib":
            gateway = BibtexLibGateway()
            strategy = BibtexImportStrategy(gateway)
        elif ext == ".ris":
            gateway = RisLibGateway()
            strategy = RisImportStrategy(gateway)
        elif ext == ".csv":
            # 1. Detect CSV Type
            with open(args.file, "r", encoding="utf-8") as f:
                header = f.readline().lower()
                if "item title" in header:
                    gateway = SpringerCsvLibGateway()
                    strategy = SpringerCsvImportStrategy(gateway)
                elif "document title" in header:
                    gateway = IeeeCsvLibGateway()
                    strategy = IeeeCsvImportStrategy(gateway)
                elif "title" in header and "doi" in header:
                    gateway = CanonicalCsvLibGateway()
                    strategy = CanonicalCsvImportStrategy(gateway)
                else:
                    print("Error: Unknown CSV format for normalization.")
                    return
        else:
            print(f"Error: Unsupported file extension {ext}")
            return

        print(f"Parsing {args.file}...")
        papers = list(strategy.fetch_papers(args.file))

        # 2. Write to Canonical
        canon_gw = CanonicalCsvLibGateway()
        canon_gw.write_file(iter(papers), args.output)
        print(f"Normalization complete. Saved {len(papers)} items to {args.output}")

    def _handle_backup(self, args):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        service = BackupService(gateway)

        print(f"Starting System Backup to {args.output}...")
        try:
            service.backup_system(args.output)
            print(f"Backup complete: {args.output}")
        except Exception as e:
            print(f"Backup failed: {e}", file=sys.stderr)
