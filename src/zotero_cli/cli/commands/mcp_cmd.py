import argparse
from typing import Any, Dict, List, Optional

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.exceptions import UsageError


def describe_cli(command: Optional[List[str]]) -> Dict[str, Any]:
    """The `schema` document, or one command of it, for the describe_cli tool."""
    from zotero_cli.cli.main import build_parser
    from zotero_cli.cli.schema import build_schema, find_command

    schema = build_schema(build_parser())
    if not command:
        return schema
    node = find_command(schema, command)
    if node is None:
        raise UsageError(f"Unknown command '{' '.join(command)}'.")
    return {
        "schema_version": schema["schema_version"],
        "version": schema["version"],
        "command": node,
    }


@CommandRegistry.register
class McpCommand(BaseCommand):
    name = "mcp"
    help = "Serve the library to AI clients over MCP (needs the 'mcp' extra)"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="verb", help="MCP subcommands")
        serve_p = subparsers.add_parser(
            "serve",
            help="Run an MCP server on stdin/stdout for an AI client",
            description="Starts a Model Context Protocol server that an AI client (Claude Desktop, Claude Code, Cursor, LM Studio, ...) launches and talks to over stdin/stdout, so it can read your library: search (including inside PDFs, with --offline), look at items, collections, tags, annotations and PDF text, and format references. All of its tools are read-only, and nothing listens on a network port. Needs the optional extra: pip install 'zotero-command-line[mcp]'.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples
--------
Scenario: Letting an AI client search my library
Problem: I want Claude Desktop to find papers in my Zotero library.
Action:  add to the client's MCP configuration: {"command": "zotero-cli", "args": ["mcp", "serve"]}
Result:  The client starts the server itself and can call search_items, get_item, get_annotations and the other read-only tools.

Scenario: The same, against the local database
Action:  {"command": "zotero-cli", "args": ["--offline", "mcp", "serve"]}
Result:  Reads come from the local zotero.sqlite with no network, and full-text search becomes available.

Notes
-----
• This command is started by your AI client from its configuration, not by hand: stdout carries the protocol, so run it in a terminal only to check that it starts (it then waits for a client).
• Everything the tools return from your library (titles, notes, annotations, PDF text) is untrusted data that other people may have written, for example in a shared group library; the server tells the client not to follow instructions in it, but only connect clients you trust with the library.
• Common Failure Modes: the extra isn't installed (the command prints the install line); no API key or library configured (run `zotero-cli init`).

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/mcp_serve.md
""",
        )
        serve_p.set_defaults(verb="serve")

    def execute(self, args: argparse.Namespace) -> None:
        if getattr(args, "verb", None) != "serve":
            raise UsageError("Run `zotero-cli mcp serve`.")
        # Imported here: nothing below is needed unless the server really starts.
        from zotero_cli.core.services.agent_tools import AgentTools
        from zotero_cli.core.services.search_service import SearchService
        from zotero_cli.infra.factory import GatewayFactory
        from zotero_cli.infra.mcp_server import build_server, run_stdio

        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        collections = GatewayFactory.get_collection_service(force_user=force_user)
        export = GatewayFactory.get_export_service(force_user=force_user)
        tools = AgentTools(
            search=SearchService(gateway),
            items=gateway,
            collections=gateway,
            tags=gateway,
            attachments=gateway,
            text=GatewayFactory.get_attachment_service(force_user=force_user),
            resolve_collection=collections.resolve_collection,
            format_bibliography=export.serialize_bibliography,
            describe_cli=describe_cli,
        )
        run_stdio(build_server(tools))
