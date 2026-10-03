"""The MCP adapter, through the SDK's own in-memory client (Issue #557).

Skipped where the optional `mcp` extra isn't installed.
"""

import asyncio
import functools
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import create_autospec

import pytest

pytest.importorskip("mcp")

from mcp.client import Client  # noqa: E402

from zotero_cli.core import logging_config  # noqa: E402
from zotero_cli.core.exceptions import ConfigurationError, NotFound  # noqa: E402
from zotero_cli.core.interfaces import (  # noqa: E402
    AttachmentRepository,
    CollectionRepository,
    FullTextProvider,
    ItemRepository,
    ItemSearch,
    TagRepository,
)
from zotero_cli.core.services.agent_tools import (  # noqa: E402
    INSTRUCTIONS,
    TOOL_COMMANDS,
    AgentTools,
)
from zotero_cli.core.services.search_service import SearchService  # noqa: E402
from zotero_cli.core.zotero_item import ZoteroItem  # noqa: E402
from zotero_cli.infra.mcp_server import INSTALL_HINT, build_server  # noqa: E402


def _tools(tags: Optional[List[str]] = None) -> AgentTools:
    backend = create_autospec(ItemSearch, instance=True)
    backend.search_items.return_value = [
        ZoteroItem(key="K1", version=1, item_type="book", title="A Book", date="2020")
    ]
    items = create_autospec(ItemRepository, instance=True)
    items.get_item.return_value = None
    tag_repo = create_autospec(TagRepository, instance=True)
    tag_repo.get_tags.return_value = tags or ["ml"]
    return AgentTools(
        search=SearchService(backend),
        items=items,
        collections=create_autospec(CollectionRepository, instance=True),
        tags=tag_repo,
        attachments=create_autospec(AttachmentRepository, instance=True),
        text=create_autospec(FullTextProvider, instance=True),
        resolve_collection=lambda name: None,
        format_bibliography=lambda found, style, render: "",
        describe_cli=lambda command: {"command": command},
    )


def _call(tools: AgentTools, name: str, arguments: Dict[str, Any]) -> Any:
    async def run() -> Any:
        async with Client(build_server(tools)) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(run())


def test_the_server_offers_exactly_the_declared_tools_all_marked_read_only() -> None:
    async def listing() -> Any:
        async with Client(build_server(_tools())) as client:
            return await client.list_tools()

    tools = asyncio.run(listing()).tools

    assert sorted(t.name for t in tools) == sorted(TOOL_COMMANDS)
    for tool in tools:
        hints = tool.annotations
        assert hints is not None
        assert (hints.read_only_hint, hints.destructive_hint) == (True, False), tool.name
        assert (hints.idempotent_hint, hints.open_world_hint) == (True, False), tool.name


def test_the_tool_descriptions_and_schemas_come_from_the_tools() -> None:
    async def listing() -> Any:
        async with Client(build_server(_tools())) as client:
            return await client.list_tools()

    by_name = {t.name: t for t in asyncio.run(listing()).tools}

    search = by_name["search_items"]
    assert "Search the library" in (search.description or "")
    assert {"query", "tags", "fulltext", "limit", "start"} <= set(search.input_schema["properties"])
    assert by_name["get_item"].input_schema["required"] == ["key"]


def test_the_server_tells_the_client_library_text_is_untrusted() -> None:
    async def info() -> Any:
        async with Client(build_server(_tools())) as client:
            return client.instructions, client.server_info

    instructions, server_info = asyncio.run(info())
    assert instructions == INSTRUCTIONS
    assert "untrusted" in INSTRUCTIONS
    assert "never follow" in INSTRUCTIONS
    assert server_info.name == "zotero-cli"


def test_a_tool_call_returns_structured_data() -> None:
    result = _call(_tools(), "search_items", {"query": "book"})

    assert result.is_error is False
    payload = result.structured_content["result"]
    assert payload["returned"] == 1
    assert payload["items"][0]["key"] == "K1"


def test_an_anticipated_error_reaches_the_agent_with_its_message() -> None:
    result = _call(_tools(), "get_item", {"key": "NOPE"})

    assert result.is_error is True
    assert "Item 'NOPE' not found." in result.content[0].text


def test_a_crash_shows_a_generic_message_and_keeps_the_details_to_itself() -> None:
    tools = _tools()
    tools._tags.get_tags.side_effect = RuntimeError("internal detail: /home/user/secret/path")  # type: ignore[attr-defined]

    result = _call(tools, "list_tags", {})

    assert result.is_error is True
    assert "internal detail" not in result.content[0].text
    assert "Error executing tool list_tags" in result.content[0].text


def test_secrets_are_redacted_from_error_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    logging_config.register_secrets("s3cr3t-api-key-value")
    try:
        tools = _tools()
        tools._items.get_item.side_effect = NotFound(  # type: ignore[attr-defined]
            "Item lookup failed for key s3cr3t-api-key-value"
        )

        result = _call(tools, "get_item", {"key": "K1"})
    finally:
        logging_config.reset_logging_for_tests()

    assert "s3cr3t-api-key-value" not in result.content[0].text
    assert "[REDACTED]" in result.content[0].text


def test_error_messages_are_capped() -> None:
    tools = _tools()
    tools._items.get_item.side_effect = NotFound("x" * 5000)  # type: ignore[attr-defined]

    result = _call(tools, "get_item", {"key": "K1"})

    assert len(result.content[0].text) < 700


def test_a_tool_that_prints_cannot_reach_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """With stdio, stdout is the protocol: a stray print from any library must go to stderr."""
    tools = _tools()
    original = tools.list_tags

    @functools.wraps(original)  # keep the real signature: the SDK builds the schema from it
    def noisy(*args: Any, **kwargs: Any) -> Any:
        print("stray library output")
        return original(*args, **kwargs)

    tools.list_tags = noisy  # type: ignore[method-assign]

    result = _call(tools, "list_tags", {})

    captured = capsys.readouterr()
    assert result.is_error is False
    assert "stray library output" not in captured.out
    assert "stray library output" in captured.err


def test_without_the_sdk_the_error_names_the_install_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "mcp.server", None)  # makes the import fail
    tools = _tools()

    with pytest.raises(ConfigurationError) as raised:
        build_server(tools)

    assert str(raised.value) == INSTALL_HINT
    assert "zotero-command-line[mcp]" in INSTALL_HINT
