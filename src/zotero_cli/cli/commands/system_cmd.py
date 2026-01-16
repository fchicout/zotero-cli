import argparse

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.commands.info_cmd import InfoCommand
from zotero_cli.cli.commands.list_cmd import ListCommand


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

    def execute(self, args: argparse.Namespace):
        if args.verb == "info":
            InfoCommand().execute(args)
        elif args.verb == "groups":
            args.list_type = "groups"
            ListCommand().execute(args)
