import argparse

import uvicorn

from zotero_cli.cli.base import BaseCommand, CommandRegistry


@CommandRegistry.register
class ServeCommand(BaseCommand):
    name = "serve"
    help = "Start the local API server"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--host", default="127.0.0.1", help="Bind host (Default: 127.0.0.1)")
        parser.add_argument("--port", type=int, default=1969, help="Bind port (Default: 1969)")
        parser.add_argument("--reload", action="store_true", help="Enable auto-reload (Dev mode)")

    def execute(self, args: argparse.Namespace):
        print(f"Starting Zotero CLI API on http://{args.host}:{args.port}")

        # Enforce security veto: If not localhost, warn/block if needed.
        # But for now, we just respect the flag, default is safe.

        uvicorn.run(
            "zotero_cli.api.main:create_app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            factory=True,
        )
