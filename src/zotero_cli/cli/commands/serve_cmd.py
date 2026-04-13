import argparse

import uvicorn

from zotero_cli.cli.base import BaseCommand, CommandRegistry


@CommandRegistry.register
class ServeCommand(BaseCommand):
    name = "serve"
    help = "Start the local API server"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.description = "Starts a local HTTP API server that exposes your Zotero library and semantic search capabilities via standard REST endpoints."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Connecting Zotero to a custom research dashboard
Problem: I'm building a web app to track my research progress and I need a way to fetch item data from Zotero via JavaScript.
Action:  zotero-cli serve --host 0.0.0.0 --port 8000
Result:  The API is now reachable at http://localhost:8000, providing JSON responses for my library queries.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to bind to a port already in use.
• Safety Tips: Default bind is 127.0.0.1 (Localhost). If using 0.0.0.0, ensure your network is secure as it exposes research metadata.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/serve.md
"""
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
