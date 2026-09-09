import sys


def verify_environment() -> None:
    """
    Ensure the runtime environment meets minimum requirements before loading dependencies.
    """
    if sys.version_info < (3, 11):
        error_msg = (
            "Incompatible Environment Detected\n\n"
            "Zotero CLI requires Python 3.11 or higher.\n"
            f"Current version: {sys.version}."
        )
        try:
            from rich.console import Console
            from rich.panel import Panel

            console = Console(stderr=True)
            console.print(Panel(f"[bold red]{error_msg}[/bold red]", border_style="red"))
        except ImportError:
            print(f"ERROR: {error_msg}", file=sys.stderr)
        sys.exit(1)


# Run pre-flight checks before importing internal modules
verify_environment()

import argparse  # noqa: E402

from zotero_cli.cli import commands  # noqa: F401, E402 (Trigger registration)
from zotero_cli.cli.base import CommandRegistry  # noqa: E402
from zotero_cli.core.config import get_config  # noqa: E402
from zotero_cli.core.exceptions import ConfigurationError  # noqa: E402

# --- Global State ---
FORCE_USER = False
OFFLINE_MODE = False

# --- Main Router ---


def main() -> None:
    parser = argparse.ArgumentParser(description="Zotero CLI - The Systematic Review Engine")
    parser.add_argument("--user", action="store_true", help="Force Personal Library mode")
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Use local zotero.sqlite database (read-only). Operates across "
            "the entire local database, not just the configured library - "
            "see docs/ARCHITECTURE.md if more than one library is synced "
            "locally."
        ),
    )
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

    global FORCE_USER, OFFLINE_MODE
    FORCE_USER = args.user
    OFFLINE_MODE = args.offline

    try:
        # Initialize global config with potential path override - inside
        # the same handling as command dispatch below, since a malformed
        # config.toml now raises ConfigurationError here (Issue #290)
        # rather than being silently swallowed to an empty config. Skipped
        # for `init`, which is the dedicated recovery path for a missing
        # or broken config file and never reads the global config itself -
        # eagerly parsing here would block a user from ever reaching `init`
        # to fix a config.toml that's actually broken.
        if getattr(args, "command", None) != "init":
            get_config(args.config)

        if hasattr(args, "func"):
            args.func(args)
        else:
            parser.print_help()
    except ConfigurationError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
