import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.config import ConfigLoader, ZoteroConfig
from zotero_cli.infra.factory import GatewayFactory


@CommandRegistry.register
class InitCommand(BaseCommand):
    name = "init"
    help = "Interactive configuration wizard"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--force", action="store_true", help="Overwrite existing config")

    def execute(self, args: argparse.Namespace):
        console = Console()
        console.rule("[bold blue]Zotero CLI Configuration Wizard[/]")

        # 1. Determine Path
        custom_path = Path(args.config) if args.config else None
        loader = ConfigLoader(config_path=custom_path)
        config_path = loader.config_path

        if config_path.exists() and not args.force:
            console.print(f"[yellow]Config file already exists at: {config_path}[/]")
            if not Confirm.ask("Do you want to overwrite it?"):
                console.print("[red]Aborted.[/]")
                return

        # 2. Interactive Prompts
        console.print(
            "[italic]Please find your API Key and Library ID at https://www.zotero.org/settings/keys[/]\n"
        )

        api_key = Prompt.ask("Enter your Zotero API Key", password=True)
        lib_type = Prompt.ask("Library Type", choices=["user", "group"], default="group")
        lib_id = Prompt.ask("Library ID (User ID or Group ID)")

        user_id = ""
        if lib_type == "group":
            user_id = Prompt.ask(
                "Your personal User ID (optional, used for '--user' mode)", default=""
            )

        target_group = ""
        if lib_type == "group":
            target_group = Prompt.ask(
                "Target Group Name (slug from URL, e.g. 'my-research-group')", default=""
            )

        console.print("\n[bold]Advanced Services (Optional)[/]")
        ss_key = Prompt.ask("Semantic Scholar API Key", default="")
        up_email = Prompt.ask("Unpaywall Email", default="")

        # 3. Verification
        console.print("\n[yellow]Verifying credentials...[/]")
        temp_config = ZoteroConfig(
            api_key=api_key,
            library_id=lib_id,
            library_type=lib_type,
            user_id=user_id if user_id else None,
            target_group_url=target_group if target_group else None,
            semantic_scholar_api_key=ss_key if ss_key else None,
            unpaywall_email=up_email if up_email else None,
        )

        try:
            client = GatewayFactory.get_zotero_gateway(config=temp_config)
            # Try a simple request to verify
            # We use items with limit 1 as a lightweight check
            client.http.get("items", params={"limit": 1})
            console.print("[green]✔ Credentials verified successfully![/]")
        except Exception as e:
            console.print(f"[bold red]✘ Verification failed:[/] {e}")
            if not Confirm.ask("Do you want to save the configuration anyway?"):
                console.print("[red]Aborted.[/]")
                return

        # 4. Construct TOML content
        toml_content = [
            "# Zotero CLI Configuration",
            "[zotero]",
            f'api_key = "{api_key}"',
            f'library_id = "{lib_id}"',
            f'library_type = "{lib_type}"',
        ]
        if user_id:
            toml_content.append(f'user_id = "{user_id}"')
        if target_group:
            toml_content.append(f'target_group = "{target_group}"')
        if ss_key:
            toml_content.append(f'semantic_scholar_api_key = "{ss_key}"')
        if up_email:
            toml_content.append(f'unpaywall_email = "{up_email}"')

        # 5. Save
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                f.write("\n".join(toml_content) + "\n")

            console.print(f"\n[green]✔ Configuration saved to:[/] {config_path}")
            console.print("\n[bold]Next Steps:[/]")
            console.print("1. Run [cyan]zotero-cli system info[/] to check your setup.")
            console.print("2. Run [cyan]zotero-cli collection list[/] to see your collections.")
            console.print("3. Happy researching!")

        except Exception as e:
            console.print(f"[bold red]Failed to save config: {e}[/]", file=sys.stderr)