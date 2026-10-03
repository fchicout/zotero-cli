"""`zotero-cli mcp serve`: wiring, the missing extra, describe_cli (Issue #557)."""

import argparse
import sys
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.mcp_cmd import McpCommand, describe_cli
from zotero_cli.cli.main import build_parser
from zotero_cli.cli.schema import COMMAND_EFFECTS
from zotero_cli.core.exceptions import ConfigurationError, UsageError
from zotero_cli.core.services.agent_tools import AgentTools


def test_the_verb_parses() -> None:
    assert build_parser().parse_args(["mcp", "serve"]).verb == "serve"
    assert build_parser().parse_args(["--offline", "mcp", "serve"]).offline is True


def test_mcp_without_a_verb_says_what_to_run() -> None:
    command = McpCommand()
    args = argparse.Namespace(verb=None)
    with pytest.raises(UsageError, match="zotero-cli mcp serve"):
        command.execute(args)


def test_serve_is_classified_as_read_only() -> None:
    assert COMMAND_EFFECTS["mcp serve"] == "read"


def _factories() -> Any:
    return (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_export_service"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_attachment_service"),
    )


def test_serve_builds_the_tools_from_the_factories_and_runs_stdio() -> None:
    built: List[Any] = []
    fake_server = MagicMock(spec_set=["run"])

    def build(tools: AgentTools) -> Any:
        built.append(tools)
        return fake_server

    gateway, collections, export, attachments = _factories()
    with (
        gateway as get_gateway,
        collections,
        export,
        attachments,
        patch("zotero_cli.infra.mcp_server.build_server", side_effect=build),
        patch("zotero_cli.infra.mcp_server.run_stdio") as run,
    ):
        McpCommand().execute(argparse.Namespace(verb="serve", user=True))

    assert len(built) == 1
    assert isinstance(built[0], AgentTools)
    run.assert_called_once_with(fake_server)
    get_gateway.assert_called_once_with(force_user=True)


def test_serve_without_the_extra_prints_the_install_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "mcp.server", None)  # as if the SDK were not installed
    gateway, collections, export, attachments = _factories()
    command = McpCommand()
    args = argparse.Namespace(verb="serve", user=False)

    with gateway, collections, export, attachments:
        with pytest.raises(ConfigurationError, match=r"zotero-command-line\[mcp\]"):
            command.execute(args)


def test_describe_cli_returns_the_whole_schema_or_one_command() -> None:
    whole = describe_cli(None)
    assert whole["program"] == "zotero-cli"
    assert any(c["name"] == "mcp" for c in whole["commands"])

    one = describe_cli(["search"])
    assert one["command"]["path"] == ["search"]
    assert one["command"]["effect"] == "read"


def test_describe_cli_for_an_unknown_command_is_a_usage_error() -> None:
    with pytest.raises(UsageError, match="Unknown command 'nonsense'"):
        describe_cli(["nonsense"])
