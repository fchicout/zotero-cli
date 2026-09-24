import argparse
import os
import secrets
import sys

import uvicorn

from zotero_cli.cli.base import BaseCommand, CommandRegistry


@CommandRegistry.register
class ServeCommand(BaseCommand):
    name = "serve"
    help = "Start the local API server"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Starts a local, read-only HTTP API server that exposes your Zotero library through REST endpoints."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Connecting Zotero to a custom research dashboard
Problem: I'm building a web app to track my research progress and I need a way to fetch item data from Zotero via JavaScript.
Action:  zotero-cli serve --port 8000
Result:  The API is reachable at http://127.0.0.1:8000 (or http://localhost:8000) from this machine only, returning JSON for library queries.

Scenario: Reaching the API from another machine
Problem: My dashboard runs on a different host on my home network.
Action:  zotero-cli serve --host 0.0.0.0 --allow-remote
Result:  The server prints an access token once. Every request must send `Authorization: Bearer <token>`.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to bind to a port already in use. Requests with a Host header other than 127.0.0.1/localhost/::1 get 400 unless added with --allowed-host (e.g. a custom local hostname).
• Safety Tips: The API has no user accounts. The default bind (127.0.0.1) keeps it on this machine. A non-loopback --host is refused unless you pass --allow-remote, which requires a bearer token on every request. Only do that on a network you trust: the traffic is plain HTTP.
• Scope: One `serve` process targets exactly one Zotero library (whichever `--config`/`--user`/`system switch` resolves at startup) - it is not multi-tenant. For HTTP access to more than one library, run a separate `serve` instance per library on a different port.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/serve.md
"""
        parser.add_argument("--host", default="127.0.0.1", help="Bind host (Default: 127.0.0.1)")
        parser.add_argument("--port", type=int, default=1969, help="Bind port (Default: 1969)")
        parser.add_argument("--reload", action="store_true", help="Enable auto-reload (Dev mode)")
        parser.add_argument(
            "--allow-remote",
            action="store_true",
            help="Allow a non-loopback --host; every request then needs the printed bearer token",
        )
        parser.add_argument(
            "--allowed-host",
            action="append",
            default=[],
            metavar="HOST",
            help="Extra Host header value to accept (repeatable), e.g. a local hostname",
        )

    def execute(self, args: argparse.Namespace) -> None:
        from zotero_cli.api.main import (
            ENV_ALLOWED_HOSTS,
            ENV_TOKEN,
            LOOPBACK_HOSTS,
            is_loopback_host,
        )

        remote = not is_loopback_host(args.host)
        if remote and not args.allow_remote:
            print(
                f"Refusing to bind to {args.host}: that exposes your library to the network. "
                "Use the default 127.0.0.1, or pass --allow-remote to require a bearer token.",
                file=sys.stderr,
            )
            sys.exit(2)

        allowed_hosts = list(LOOPBACK_HOSTS) + list(args.allowed_host)
        os.environ.pop(ENV_TOKEN, None)
        if remote:
            # Remote clients reach the server by any address or name, so the
            # token, not the Host header, is what protects it here.
            if not args.allowed_host:
                allowed_hosts = ["*"]
            token = secrets.token_urlsafe(32)
            os.environ[ENV_TOKEN] = token
            print("Remote access enabled. Send this header with every request:")
            print(f"  Authorization: Bearer {token}")
            print("The token changes every time the server starts.")
        os.environ[ENV_ALLOWED_HOSTS] = ",".join(allowed_hosts)

        print(f"Starting Zotero CLI API on http://{args.host}:{args.port}")
        uvicorn.run(
            "zotero_cli.api.main:create_app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            factory=True,
        )
