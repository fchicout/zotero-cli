import argparse
import sys
from typing import Optional
from pathlib import Path

from zotero_cli.core.config import get_config, ZoteroConfig, reset_config
from zotero_cli.cli.base import CommandRegistry
import zotero_cli.cli.commands # Trigger registration

# --- Global State ---
FORCE_USER = False

# --- Command Routing (v2.0 Transition) ---

def handle_legacy_routing():
    if len(sys.argv) < 2:
        return

    mapping = {
        "decide": ["review", "decide"],
        "d": ["review", "decide"], # Alias support
        "screen": ["review", "screen"],
        "inspect": ["item", "inspect"],
        "info": ["system", "info"],
    }
    
    cmd = sys.argv[1]
    
    if cmd in mapping:
        new_cmd = mapping[cmd]
        print(f"[DEPRECATED] '{cmd}' is now 'zotero-cli {' '.join(new_cmd)}'.", file=sys.stderr)
        sys.argv[1:2] = new_cmd
    elif cmd == "manage" and len(sys.argv) > 2:
        sub = sys.argv[2]
        if sub == "move":
            print(f"[DEPRECATED] 'manage move' is now 'item move'.", file=sys.stderr)
            sys.argv[1:3] = ["item", "move"]
        elif sub == "clean":
            print(f"[DEPRECATED] 'manage clean' is now 'collection clean'.", file=sys.stderr)
            sys.argv[1:3] = ["collection", "clean"]
    elif cmd == "list" and len(sys.argv) > 2 and sys.argv[2] == "groups":
        print(f"[DEPRECATED] 'list groups' is now 'system groups'.", file=sys.stderr)
        sys.argv[1:3] = ["system", "groups"]

# --- Main Router ---

def main():
    handle_legacy_routing()
    parser = argparse.ArgumentParser(description="Zotero CLI - The Systematic Review Engine")
    parser.add_argument("--user", action="store_true", help="Force Personal Library mode")
    parser.add_argument("--config", help="Path to a custom config.toml")
    subparsers = parser.add_subparsers(dest='command', help='Primary Commands')
    
    # --- Registered Commands ---
    # Sort by name for consistent help output
    commands = sorted(CommandRegistry.get_commands(), key=lambda x: x.name)
    for cmd in commands:
        aliases = getattr(cmd, 'aliases', [])
        cmd_parser = subparsers.add_parser(cmd.name, help=cmd.help, aliases=aliases)
        cmd.register_args(cmd_parser)
        cmd_parser.set_defaults(func=cmd.execute)

    args = parser.parse_args()
    
    global FORCE_USER
    FORCE_USER = args.user

    # Initialize global config with potential path override
    get_config(args.config)

    if hasattr(args, 'func'):
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
