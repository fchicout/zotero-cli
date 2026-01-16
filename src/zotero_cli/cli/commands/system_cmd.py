import argparse
import sys

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.commands.info_cmd import InfoCommand
from zotero_cli.cli.commands.list_cmd import ListCommand
from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.infra.factory import GatewayFactory


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
        norm_p = sub.add_parser("normalize", help="Convert external CSV (IEEE, Springer) to Canonical format")
        norm_p.add_argument("file", help="Input CSV file")
        norm_p.add_argument("--output", required=True, help="Output Canonical CSV path")

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

    def _handle_normalize(self, args):
        from zotero_cli.core.strategies import (
            CanonicalCsvImportStrategy,
            IeeeCsvImportStrategy,
            SpringerCsvImportStrategy,
        )
        from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway
        from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
        from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway

        # 1. Detect and Load
        with open(args.file, 'r', encoding='utf-8') as f:
            header = f.readline().lower()
            if 'item title' in header:
                gateway = SpringerCsvLibGateway()
                strategy = SpringerCsvImportStrategy(gateway)
            elif 'document title' in header:
                gateway = IeeeCsvLibGateway()
                strategy = IeeeCsvImportStrategy(gateway)
            elif 'title' in header and 'doi' in header:
                gateway = CanonicalCsvLibGateway()
                strategy = CanonicalCsvImportStrategy(gateway)
            else:
                print("Error: Unknown CSV format for normalization.")
                return

        print(f"Parsing {args.file}...")
        papers = list(strategy.fetch_papers(args.file))

        # 2. Write to Canonical
        canon_gw = CanonicalCsvLibGateway()
        canon_gw.write_file(iter(papers), args.output)
        print(f"Normalization complete. Saved {len(papers)} items to {args.output}")

    def _handle_backup(self, args):
        force_user = getattr(args, 'user', False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        service = BackupService(gateway)

        print(f"Starting System Backup to {args.output}...")
        try:
            service.backup_system(args.output)
            print(f"Backup complete: {args.output}")
        except Exception as e:
            print(f"Backup failed: {e}", file=sys.stderr)
