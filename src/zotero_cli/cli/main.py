import argparse
import sys

from zotero_cli.cli import commands  # noqa: F401 (Trigger registration)
from zotero_cli.cli.base import CommandRegistry
from zotero_cli.core.config import get_config

# --- Global State ---
FORCE_USER = False

# --- Main Router ---


def main():
    parser = argparse.ArgumentParser(description="Zotero CLI - The Systematic Review Engine")
    parser.add_argument("--user", action="store_true", help="Force Personal Library mode")
    parser.add_argument("--config", help="Path to a custom config.toml")
    subparsers = parser.add_subparsers(dest="command", help="Primary Commands")

    # --- Registered Commands ---
    # Sort by name for consistent help output
    registered_commands = sorted(CommandRegistry.get_commands(), key=lambda x: x.name)
    for cmd in registered_commands:
        aliases = getattr(cmd, "aliases", [])
        cmd_parser = subparsers.add_parser(cmd.name, help=cmd.help, aliases=aliases)
        cmd.register_args(cmd_parser)
        cmd_parser.set_defaults(func=cmd.execute)

    args = parser.parse_args()

    global FORCE_USER
    FORCE_USER = args.user

    # Initialize global config with potential path override
    get_config(args.config)

    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
