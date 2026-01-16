import argparse
from zotero_cli.cli.base import BaseCommand, CommandRegistry

@CommandRegistry.register
class ReviewCommand(BaseCommand):
    name = "review"
    help = "Systematic Review Workflow (Screening, Auditing)"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)
        
        from zotero_cli.cli.commands.screen_cmd import ScreenCommand, DecideCommand
        
        # Screen
        screen_p = sub.add_parser("screen", help=ScreenCommand.help)
        ScreenCommand().register_args(screen_p)

        # Decide
        decide_p = sub.add_parser("decide", help=DecideCommand.help)
        DecideCommand().register_args(decide_p)

    def execute(self, args: argparse.Namespace):
        from zotero_cli.cli.commands.screen_cmd import ScreenCommand, DecideCommand
        
        if args.verb == "screen":
            ScreenCommand().execute(args)
        elif args.verb == "decide":
            DecideCommand().execute(args)