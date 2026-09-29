import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict

import toml
from rich.markup import escape
from rich.prompt import Confirm, Prompt

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.config import ConfigLoader, ZoteroConfig, secure_config_open, tomllib
from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.logging_config import redact, register_secrets
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup
from zotero_cli.infra.factory import GatewayFactory


@CommandRegistry.register
class InitCommand(BaseCommand):
    name = "init"
    help = "Interactive configuration wizard"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Launches an interactive setup wizard to configure the Zotero CLI, establishing connection credentials and local storage paths."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Examples
--------
Scenario: First-time setup of the CLI
Problem: I've just installed the zotero-cli and I need to connect it to my Zotero account.
Action:  zotero-cli init
Result:  The CLI asks for my API key and Library ID, then creates the configuration file.

Notes
-----
• Common Failure Modes: Providing an incorrect API key or ID during the wizard. The CLI will attempt to validate these via a heartbeat request to the API.
• Safety Tips: Keep your API key private. The init command stores it in a plain-text config.toml file by default, so ensure your configuration directory has restricted access permissions.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/init.md
"""
        parser.add_argument(
            "--force", action="store_true", help="Update an existing config without asking"
        )

    def execute(self, args: argparse.Namespace) -> None:
        console = Console()
        console.rule("[bold blue]Zotero CLI Configuration Wizard[/]")

        # 1. Determine Path
        custom_path = Path(args.config) if args.config else None
        loader = ConfigLoader(config_path=custom_path)
        config_path = loader.config_path

        # An existing config is updated, not replaced: keys the wizard
        # doesn't ask about (AI keys, ncbi_api_key, storage_path, other
        # tables) are kept, and its values are the defaults (Issue #388).
        document: Dict[str, Any] = {}
        if config_path.exists():
            document = _read_existing(config_path, console)
            if not args.force:
                console.print(
                    f"[yellow]Config file already exists at: {safe_markup(config_path)}[/]"
                )
                if not Confirm.ask("Update it? Settings you don't change are kept"):
                    console.print("[red]Aborted.[/]")
                    return
        current: Dict[str, Any] = document.setdefault("zotero", {})

        # 2. Interactive Prompts
        console.print(
            "[italic]Please find your API Key and Library ID at https://www.zotero.org/settings/keys[/]\n"
        )

        existing_key = str(current.get("api_key") or "")
        api_key = Prompt.ask(
            "Enter your Zotero API Key" + (" (Enter keeps the current one)" if existing_key else ""),
            password=True,
            default=existing_key or None,
            show_default=False,
        )
        if not api_key:
            raise UsageError("An API key is required: create one at https://www.zotero.org/settings/keys")
        register_secrets(api_key)

        # Resolve the key's owning identity up front - no library_id needed
        # for this call (Issue #178) - so we can confirm the key itself is
        # valid and prefill the personal userID before asking for it.
        resolved_user_id = ""
        try:
            from zotero_cli.infra.zotero_api import ZoteroAPIClient

            identity = ZoteroAPIClient.resolve_key_identity(api_key)
            resolved_user_id = str(identity.user_id)
            console.print(
                f"[green]✔ Key belongs to '{safe_markup(identity.username)}' (User ID: {safe_markup(identity.user_id)})[/]\n"
            )
        except Exception as e:
            console.print(
                f"[yellow]⚠ Could not resolve key identity yet: {escape(redact(str(e)))}[/]\n"
            )

        # Most first-time users have a personal library (Issue #397).
        lib_type = Prompt.ask(
            "Library Type",
            choices=["user", "group"],
            default=str(current.get("library_type") or "user"),
        )
        if lib_type == "user":
            lib_id = Prompt.ask(
                "Library ID (your User ID)",
                default=resolved_user_id or str(current.get("library_id") or "") or None,
            )
        else:
            lib_id = _ask_group_id(console, str(current.get("library_id") or ""))

        user_id = ""
        if lib_type == "group":
            user_id = Prompt.ask(
                "Your personal User ID (optional, used for '--user' mode)",
                default=resolved_user_id or str(current.get("user_id") or ""),
            )

        console.print("\n[bold]Advanced Services (Optional)[/]")
        ss_key = Prompt.ask(
            "Semantic Scholar API Key", default=str(current.get("semantic_scholar_api_key") or "")
        )
        up_email = Prompt.ask("Unpaywall Email", default=str(current.get("unpaywall_email") or ""))
        database_path = Prompt.ask(
            "Path to zotero.sqlite, for --offline (optional)",
            default=str(current.get("database_path") or _default_database_path()),
        )

        # 3. Verification
        console.print("\n[yellow]Verifying credentials...[/]")
        temp_config = ZoteroConfig(
            api_key=api_key,
            library_id=lib_id,
            library_type=lib_type,
            user_id=user_id if user_id else None,
            semantic_scholar_api_key=ss_key if ss_key else None,
            unpaywall_email=up_email if up_email else None,
        )

        try:
            client = GatewayFactory.get_zotero_gateway(config=temp_config)
            # Try a simple request to verify
            if client.verify_credentials():
                console.print("[green]✔ Credentials verified successfully![/]")
            else:
                raise RuntimeError("API request returned failure status")
        except Exception as e:
            console.print(f"[bold red]✘ Verification failed:[/] {safe_markup(e)}")
            if not Confirm.ask("Do you want to save the configuration anyway?"):
                console.print("[red]Aborted.[/]")
                return

        # 4. Merge the answers. An empty optional answer leaves the key out.
        current.update({"api_key": api_key, "library_id": lib_id, "library_type": lib_type})
        # target_group was a slug the loader couldn't use; library_id wins.
        current.pop("target_group", None)
        optional = {
            "user_id": user_id,
            "semantic_scholar_api_key": ss_key,
            "unpaywall_email": up_email,
            "database_path": database_path,
        }
        for key, value in optional.items():
            if value:
                current[key] = value
            else:
                current.pop(key, None)

        # 5. Save. A TOML writer, not string formatting: a value with a quote
        # or backslash (a Windows path) broke the file, and a newline could
        # add keys (Issue #388).
        try:
            # config.toml holds live API keys - written with 0600
            # permissions from creation, not the process's default umask
            # (Issue #236).
            with secure_config_open(config_path) as f:
                f.write("# Zotero CLI Configuration\n" + toml.dumps(document))

            console.print(f"\n[green]✔ Configuration saved to:[/] {safe_markup(config_path)}")
            console.print("\n[bold]Next Steps:[/]")
            console.print("1. Run [cyan]zotero-cli system info[/] to check your setup.")
            console.print("2. Run [cyan]zotero-cli collection list[/] to see your collections.")
            console.print("3. Happy researching!")

        except Exception as e:
            console.print(f"[bold red]Failed to save config: {safe_markup(e)}[/]")
            sys.exit(1)


def _read_existing(config_path: Path, console: Console) -> Dict[str, Any]:
    try:
        with open(config_path, "rb") as f:
            return dict(tomllib.load(f))
    except (OSError, tomllib.TOMLDecodeError) as e:
        console.print(
            f"[yellow]The existing config can't be read ({safe_markup(e)}); "
            "it will be replaced.[/]"
        )
        return {}


def _ask_group_id(console: Console, default: str) -> str:
    """A group ID, or a group URL it is taken from."""
    while True:
        answer = (
            Prompt.ask(
                "Group ID or URL (https://www.zotero.org/groups/<id>/...)", default=default or None
            )
            or ""
        ).strip()
        match = re.search(r"/groups/(\d+)", answer)
        if match:
            return match.group(1)
        if answer.isdigit():
            return answer
        console.print("[red]Enter the group's number, or its URL from zotero.org.[/]")


def _default_database_path() -> str:
    """~/Zotero/zotero.sqlite when it exists (Zotero's default location on
    every OS), else empty."""
    candidate = Path.home() / "Zotero" / "zotero.sqlite"
    return str(candidate) if candidate.exists() else ""
