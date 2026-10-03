"""The MCP server: the SDK adapter for AgentTools (Issue #557).

All use of the `mcp` package is here and lazy, so the base install never needs it. The tool
logic, limits and cleaning of untrusted text are in core/services/agent_tools.py; this module
only registers the tools, marks each one read-only, and keeps stray output off the protocol
channel.
"""

import contextlib
import functools
import sys
from typing import Any, Callable, Type, TypeVar, cast

from zotero_cli import __version__
from zotero_cli.core.exceptions import ConfigurationError, ZoteroCliError
from zotero_cli.core.logging_config import redact
from zotero_cli.core.services.agent_tools import INSTRUCTIONS, TOOL_COMMANDS, AgentTools, clean

F = TypeVar("F", bound=Callable[..., Any])

INSTALL_HINT = (
    "The MCP server needs the optional 'mcp' extra: pip install 'zotero-command-line[mcp]'"
)


def _guarded(func: F, tool_error: Type[Exception]) -> F:
    """Run a tool with two protections.

    stdout goes to stderr while it runs: with the stdio transport stdout carries the
    protocol itself, so one stray line from any library would corrupt it (the transport
    holds the real stdout from the moment it starts).

    An error we anticipated (not found, bad argument, no configuration) reaches the agent
    with its message, redacted like a log line, so it can correct itself. The SDK replaces
    any other exception with a generic message and keeps the details on the server, which
    is what we want for a crash."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with contextlib.redirect_stdout(sys.stderr):
            try:
                return func(*args, **kwargs)
            except ZoteroCliError as exc:
                raise tool_error(clean(redact(str(exc)), 500)) from exc

    return cast(F, wrapper)


def build_server(tools: AgentTools) -> Any:
    """An MCPServer offering every tool in TOOL_COMMANDS, each marked read-only. Raises
    ConfigurationError, with the install line, if the SDK is missing."""
    try:
        from mcp.server import MCPServer
        from mcp.server.mcpserver.exceptions import ToolError
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise ConfigurationError(INSTALL_HINT) from exc

    server = MCPServer("zotero-cli", instructions=INSTRUCTIONS, version=__version__)
    read_only = ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,  # the library only: no tool reaches out to other services
    )
    for name in TOOL_COMMANDS:
        method = getattr(tools, name)
        server.tool(name=name, annotations=read_only)(_guarded(method, ToolError))
    return server


def run_stdio(server: Any) -> None:
    """Serve over stdio until the client disconnects."""
    server.run(transport="stdio")
