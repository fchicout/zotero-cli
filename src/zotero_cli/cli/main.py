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
            console.print(
                Panel(f"[bold red]{safe_markup(error_msg)}[/bold red]", border_style="red")
            )
        except ImportError:
            print(f"ERROR: {error_msg}", file=sys.stderr)
        sys.exit(1)


# Run pre-flight checks before importing internal modules
verify_environment()

import argparse  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
from typing import Any  # noqa: E402

from zotero_cli import __version__  # noqa: E402
from zotero_cli.cli import commands  # noqa: F401, E402 (Trigger registration)
from zotero_cli.cli.base import CommandRegistry  # noqa: E402
from zotero_cli.cli.deprecation import warn_deprecated_command  # noqa: E402
from zotero_cli.cli.notify import stderr_notify  # noqa: E402
from zotero_cli.core.config import get_config  # noqa: E402
from zotero_cli.core.exceptions import EXIT_CODES, ZoteroCliError  # noqa: E402
from zotero_cli.core.logging_config import setup_logging  # noqa: E402
from zotero_cli.core.runtime import set_offline_mode  # noqa: E402
from zotero_cli.core.utils.notify import set_default_notify  # noqa: E402
from zotero_cli.core.utils.terminal_safety import (  # noqa: E402
    make_output_streams_tolerant,
    safe_markup,
)

logger = logging.getLogger(__name__)

# --- Main Router ---


_LAST_PARSER: list["argparse.ArgumentParser | None"] = [None]


class _LeafErrorParser(argparse.ArgumentParser):
    """Reports a stray argument through the subcommand that was being
    parsed, so the usage line names it (Issue #379). Plain argparse hands
    the leftovers back to the top-level parser, which then prints the
    top-level usage - useless for `item inspect KEY --bogus`."""

    def parse_known_args(  # type: ignore[override]
        self, args: Any = None, namespace: Any = None
    ) -> Any:
        _LAST_PARSER[0] = self
        return super().parse_known_args(args, namespace)

    def parse_args(self, args: Any = None, namespace: Any = None) -> Any:  # type: ignore[override]
        _LAST_PARSER[0] = None
        parsed, extras = self.parse_known_args(args, namespace)
        if extras:
            (_LAST_PARSER[0] or self).error(f"unrecognized arguments: {' '.join(extras)}")
        return parsed


def build_parser() -> argparse.ArgumentParser:
    """The full command-line parser (also used by the docs tests to check
    that every documented example parses, Issue #386)."""
    parser = _LeafErrorParser(
        description="zotero-cli - manage your Zotero library from the command line",
        epilog=(
            "Exit status: "
            + ", ".join(f"{code} {meaning}" for code, meaning in EXIT_CODES.items())
            + ". Errors go to stderr; -v adds the traceback. See docs/EXIT_CODES.md."
        ),
    )
    parser.add_argument("-V", "--version", action="version", version=f"zotero-cli {__version__}")
    parser.add_argument("--user", action="store_true", help="Force Personal Library mode")
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Use the local zotero.sqlite database instead of the Web API. "
            "Read-only, except `item trash`/`item restore`, which write to "
            "zotero.sqlite directly (close Zotero and keep a backup first). "
            "Operates across the entire local database, not just the "
            "configured library - see docs/SETUP_GUIDE.md if more than one "
            "library is synced locally."
        ),
    )
    parser.add_argument("--config", help="Path to a custom config.toml")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug-level logging to stderr (always logged to file regardless)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Primary Commands")

    # --- Registered Commands ---
    # Sort by name for consistent help output
    registered_commands = sorted(CommandRegistry.get_commands(), key=lambda x: x.name)
    for cmd in registered_commands:
        aliases = getattr(cmd, "aliases", [])
        cmd_parser = subparsers.add_parser(cmd.name, help=cmd.help, aliases=aliases)
        cmd.register_args(cmd_parser)
        cmd_parser.set_defaults(func=cmd.execute)
    return parser


def main() -> None:
    # First, so even a usage error or --help is safe on a legacy console (#513).
    make_output_streams_tolerant()
    # Domain services speak through this sink; without it they only log (Issue #393).
    set_default_notify(stderr_notify)
    parser = build_parser()
    args = parser.parse_args()

    set_offline_mode(args.offline)

    # Issue #292: without this, logger.info/.debug calls vanish entirely
    # (default root level is WARNING with no handler) and logger.warning/
    # .exception fall through to logging.lastResort - an unformatted
    # stderr line with no persistence, leaving no way to debug a failed
    # background job (slr snowball discovery, system jobs) from logs alone.
    setup_logging(verbose=args.verbose)

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
            warn_deprecated_command(args)
            args.func(args)
        else:
            parser.print_help()
    except ZoteroCliError as e:
        # Expected failures: one line, and the exit code that says which
        # kind (Issues #368, #370, docs/EXIT_CODES.md).
        _fail(str(e), e.exit_code, args)
    except (FileNotFoundError, PermissionError, IsADirectoryError, NotADirectoryError) as e:
        _fail(f"{e.strerror}: {e.filename}" if e.filename else str(e), 1, args)
    except EOFError:
        # A prompt with no terminal to answer it (scripts, CI, agents).
        _fail(
            "this command asks for confirmation and there is no terminal to answer it; "
            "pass --force (or --yes) to run it non-interactively",
            2,
            args,
        )
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:
        # Output piped into something that stopped reading (e.g. `| head`).
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)
    except Exception as e:
        logger.exception("Unhandled exception during command dispatch")
        _fail(f"{type(e).__name__}: {e}", 1, args, unexpected=True)


def _fail(message: str, code: int, args: argparse.Namespace, unexpected: bool = False) -> None:
    """Prints one error line on stderr and exits with `code`. The traceback
    goes to stderr only with -v (it is always in the log file)."""
    message = message.strip()
    if message.lower().startswith("error:"):
        message = message[len("error:") :].strip()
    print(f"Error: {message}", file=sys.stderr)
    if getattr(args, "verbose", False):
        import traceback

        traceback.print_exc()
    elif unexpected:
        print("Run with -v for details, or see the log file.", file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
