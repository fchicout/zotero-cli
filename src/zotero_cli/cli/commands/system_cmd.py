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
