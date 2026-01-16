import argparse

from zotero_cli.cli.base import BaseCommand


class InfoCommand(BaseCommand):
    name = "info"
    help = "Display environment and configuration"

    def register_args(self, parser: argparse.ArgumentParser):
        pass # No extra args for info

    def execute(self, args: argparse.Namespace):
        from zotero_cli.core.config import get_config, get_config_path
        config = get_config(args.config)

        print("--- Zotero CLI Info ---")
        print(f"Config Path: {get_config_path() or 'None (using defaults/env)'}")
        print(f"Library ID:  {config.library_id}")
        print(f"Library Type: {config.library_type}")
        print(f"API Key:     {'********' if config.api_key else 'NOT SET'}")
        if config.target_group_url:
            print(f"Group URL:   {config.target_group_url}")
