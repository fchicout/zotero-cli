import argparse
import json

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.schema import build_schema, find_command
from zotero_cli.core.exceptions import UsageError


@CommandRegistry.register
class SchemaCommand(BaseCommand):
    name = "schema"
    help = "Describe every command, flag and exit code as JSON"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.description = (
            "Prints a machine-readable description of the whole command line as JSON, generated "
            "from the real argument parser: commands, flags with their types, defaults and choices, "
            "what each command can change, and the exit codes. For scripts and AI agents that would "
            "otherwise have to parse --help."
        )
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Examples
--------
Scenario: An agent learns what it can run
Problem: A script needs the exact flags of every command without scraping --help text.
Action:  zotero-cli schema
Result:  One JSON document on stdout: version, exit codes, global options and the command tree.

Scenario: Just one command
Action:  zotero-cli schema item list
Result:  The JSON for `item list` only (its arguments, defaults, choices and effect).

Notes
-----
• Each runnable command has an "effect": read (changes nothing), local (only this machine's files
  and state) or write (your Zotero library). A write command with "preview_by_default" only shows
  what it would do until you add --execute.
• Common Failure Modes: naming a command that doesn't exist exits with status 2.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/schema.md
"""
        parser.add_argument(
            "command_path",
            metavar="COMMAND",
            nargs="*",
            help="Limit the output to this command or group, e.g. `item list` (default: everything)",
        )

    def execute(self, args: argparse.Namespace) -> None:
        # Imported here: main imports this module while it builds the parser.
        from zotero_cli.cli.main import build_parser

        schema = build_schema(build_parser())
        words = list(getattr(args, "command_path", []) or [])
        if words:
            node = find_command(schema, words)
            if node is None:
                raise UsageError(
                    f"Unknown command '{' '.join(words)}'. Run `zotero-cli schema` for the list."
                )
            payload = {
                "schema_version": schema["schema_version"],
                "program": schema["program"],
                "version": schema["version"],
                "command": node,
            }
        else:
            payload = schema
        print(json.dumps(payload, indent=2, ensure_ascii=False))
