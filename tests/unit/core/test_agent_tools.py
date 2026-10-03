"""The tools an AI agent gets: limits, cleaning of untrusted text, errors (Issue #557).

No SDK here: AgentTools is plain logic over narrow interfaces, tested with autospec fakes.
"""

import inspect
from typing import Any, Dict, List, Optional
from unittest.mock import create_autospec

import pytest

from zotero_cli.cli.schema import COMMAND_EFFECTS
from zotero_cli.core.exceptions import NotFound, UsageError
from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    FullTextProvider,
    ItemRepository,
    ItemSearch,
    TagRepository,
)
from zotero_cli.core.services import agent_tools
from zotero_cli.core.services.agent_tools import AgentTools, clean
from zotero_cli.core.services.search_service import SearchService
from zotero_cli.core.zotero_item import ZoteroItem


class Fakes:
    def __init__(self) -> None:
        self.search_backend = create_autospec(ItemSearch, instance=True)
        self.items = create_autospec(ItemRepository, instance=True)
        self.collections = create_autospec(CollectionRepository, instance=True)
        self.tags = create_autospec(TagRepository, instance=True)
        self.attachments = create_autospec(AttachmentRepository, instance=True)
        self.text = create_autospec(FullTextProvider, instance=True)
        self.formatted: List[Any] = []
        self.known_collections: Dict[str, str] = {"Reading": "COL1", "COL1": "COL1"}

    def resolve(self, name: str) -> Optional[str]:
        return self.known_collections.get(name)

    def format(self, items: List[ZoteroItem], style: str, render: str) -> str:
        self.formatted.append((items, style, render))
        return "; ".join(i.key for i in items)

    def describe(self, command: Optional[List[str]]) -> Dict[str, Any]:
        return {"described": command}

    def tools(self) -> AgentTools:
        return AgentTools(
            search=SearchService(self.search_backend),
            items=self.items,
            collections=self.collections,
            tags=self.tags,
            attachments=self.attachments,
            text=self.text,
            resolve_collection=self.resolve,
            format_bibliography=self.format,
            describe_cli=self.describe,
        )


@pytest.fixture
def fakes() -> Fakes:
    return Fakes()


def item(key: str = "K1", **fields: Any) -> ZoteroItem:
    base: Dict[str, Any] = {
        "title": f"Title {key}",
        "item_type": "journalArticle",
        "date": "2021-05-01",
        "authors": ["Ada Lovelace"],
    }
    base.update(fields)
    return ZoteroItem(key=key, version=1, **base)


# ---- cleaning -------------------------------------------------------------------------------


def test_clean_removes_control_characters_and_caps_the_length() -> None:
    assert clean("a\x1b[31mb\x07c") == "a[31mbc"
    assert clean(None) == ""
    assert clean(12) == "12"
    assert clean("x" * 10, 5) == "xxxx…"
    assert len(clean("x" * 10, 5)) == 5
    assert clean("short", 5) == "short"


# ---- search_items ---------------------------------------------------------------------------


def test_search_returns_summaries_with_clean_capped_strings(fakes: Fakes) -> None:
    fakes.search_backend.search_items.return_value = [
        item("K1", title="Evil \x1b[31m" + "t" * 800, authors=["A" * 700] * 80)
    ]

    result = fakes.tools().search_items("evil")

    assert result["returned"] == 1
    row = result["items"][0]
    assert "\x1b" not in row["title"]
    assert len(row["title"]) <= agent_tools.TITLE_CAP
    assert len(row["authors"]) == agent_tools.LIST_CAP
    assert all(len(a) <= agent_tools.TITLE_CAP for a in row["authors"])
    assert (row["key"], row["year"], row["item_type"]) == ("K1", "2021", "journalArticle")
    assert "score" not in row


def test_search_passes_every_filter_to_the_shared_search(fakes: Fakes) -> None:
    fakes.search_backend.search_items.return_value = []

    fakes.tools().search_items(
        "attention", tags=["ml", "-old"], item_type="book", collection="Reading",
        year="2018-2022", added_since="2026-01-01", added_until="2026-02-01",
        sort="title", direction="asc",
    )  # fmt: skip

    query = fakes.search_backend.search_items.call_args.args[0]
    assert (query.q, query.tag, query.item_type, query.collection) == (
        "attention", ["ml", "-old"], "book", "COL1",
    )  # fmt: skip
    assert (query.sort, query.direction) == ("title", "asc")


def test_full_text_search_reports_scores_in_ranked_order(fakes: Fakes) -> None:
    fakes.search_backend.search_fulltext.return_value = [(item("A"), 3.5), (item("B"), 1.25)]

    result = fakes.tools().search_items("retrieval", fulltext=True)

    assert [(r["key"], r["score"]) for r in result["items"]] == [("A", 3.5), ("B", 1.25)]
    assert fakes.search_backend.search_fulltext.call_args.args[0] == "retrieval"


@pytest.mark.parametrize(
    ("limit", "expected_rows"), [(0, 1), (-5, 1), (3, 3), (10_000, agent_tools.MAX_LIMIT)]
)
def test_the_limit_is_clamped(fakes: Fakes, limit: int, expected_rows: int) -> None:
    fakes.search_backend.search_items.return_value = [item(f"K{i}") for i in range(500)]
    assert fakes.tools().search_items("x", limit=limit)["returned"] == expected_rows


def test_start_skips_results(fakes: Fakes) -> None:
    fakes.search_backend.search_items.return_value = [item(f"K{i}") for i in range(10)]
    result = fakes.tools().search_items("x", limit=2, start=3)
    assert [r["key"] for r in result["items"]] == ["K3", "K4"]
    assert result["start"] == 3


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start": -1}, "start can't be negative"),
        ({"sort": "nonsense"}, "sort must be one of"),
        ({"direction": "sideways"}, "direction must be asc or desc"),
        ({"fulltext": True, "sort": "title"}, "leave out sort and direction"),
        ({"year": "20"}, "--year"),
        ({"added_since": "yesterday"}, "added_since"),
    ],
)
def test_bad_arguments_are_usage_errors(fakes: Fakes, kwargs: Dict[str, Any], message: str) -> None:
    tools = fakes.tools()
    with pytest.raises(UsageError, match=message):
        tools.search_items("x", **kwargs)
    fakes.search_backend.search_items.assert_not_called()


def test_an_unknown_collection_is_not_found(fakes: Fakes) -> None:
    tools = fakes.tools()
    with pytest.raises(NotFound, match="Collection 'Nope' not found"):
        tools.search_items("x", collection="Nope")


# ---- get_item -------------------------------------------------------------------------------


def test_get_item_describes_attachments_and_counts_notes_without_returning_them(
    fakes: Fakes,
) -> None:
    fakes.items.get_item.return_value = item(
        "K1",
        abstract="An abstract. " + "z" * 9000,
        tags=["ml", "x"],
        collections=["COL1"],
        creators=[
            {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"},
            {"creatorType": "editor", "name": "The Institute"},
        ],
        doi="10.1/x",
    )
    fakes.items.get_item_children.return_value = [
        {"key": "ATT1", "data": {"itemType": "attachment", "title": "PDF", "contentType": "application/pdf"}},
        {"key": "N1", "data": {"itemType": "note", "note": "<p>SECRET NOTE TEXT</p>"}},
        {"key": "N2", "data": {"itemType": "note", "note": "second"}},
    ]  # fmt: skip

    record = fakes.tools().get_item("K1")

    assert record["attachments"] == [
        {"key": "ATT1", "title": "PDF", "content_type": "application/pdf"}
    ]
    assert record["notes"] == 2
    assert "SECRET NOTE TEXT" not in str(record)
    assert len(record["abstract"]) <= agent_tools.FIELD_CAP
    assert record["creators"] == [
        {"type": "author", "name": "Ada Lovelace"},
        {"type": "editor", "name": "The Institute"},
    ]
    assert (record["tags"], record["collections"], record["doi"]) == (
        ["ml", "x"],
        ["COL1"],
        "10.1/x",
    )


def test_get_item_for_an_unknown_key_is_not_found(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = None
    tools = fakes.tools()
    with pytest.raises(NotFound, match="Item 'NOPE' not found"):
        tools.get_item("NOPE")


# ---- list_items, list_collections, list_tags ------------------------------------------------


def test_list_items_in_a_collection_uses_top_level_items_and_pages(fakes: Fakes) -> None:
    fakes.collections.get_items_in_collection.return_value = iter([item(f"K{i}") for i in range(6)])

    result = fakes.tools().list_items("Reading", limit=2, start=1)

    fakes.collections.get_items_in_collection.assert_called_once_with("COL1", top_only=True)
    assert [r["key"] for r in result["items"]] == ["K1", "K2"]


def test_list_items_without_a_collection_leaves_out_attachments_and_notes(fakes: Fakes) -> None:
    fakes.search_backend.search_items.return_value = [
        item("A"), item("PDF", item_type="attachment"), item("N", item_type="note"), item("B"),
    ]  # fmt: skip

    result = fakes.tools().list_items()

    assert [r["key"] for r in result["items"]] == ["A", "B"]


def test_list_collections(fakes: Fakes) -> None:
    fakes.collections.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "One"}, "meta": {"numItems": 4}},
        {"key": "C2", "data": {"name": "Two", "parentCollection": "C1"}},
    ]

    result = fakes.tools().list_collections()

    assert result["collections"] == [
        {"key": "C1", "name": "One", "parent": "", "num_items": 4},
        {"key": "C2", "name": "Two", "parent": "C1", "num_items": 0},
    ]


def test_list_tags_sorts_filters_and_pages(fakes: Fakes) -> None:
    fakes.tags.get_tags.return_value = ["zeta", "Alpha", "machine learning", "alpha2"]

    tools = fakes.tools()

    assert tools.list_tags()["tags"] == ["Alpha", "alpha2", "machine learning", "zeta"]
    only = tools.list_tags(contains="ALPHA")
    assert (only["tags"], only["total"]) == (["Alpha", "alpha2"], 2)
    page = tools.list_tags(limit=1, start=1)
    assert (page["tags"], page["total"]) == (["alpha2"], 4)


# ---- get_annotations ------------------------------------------------------------------------


def _annotation(key: str, kind: str, **extra: str) -> Dict[str, Any]:
    from zotero_cli.core import annotations

    return annotations.build(key, "PDF1", kind, **extra)


def test_annotations_are_cleaned_capped_and_filtered_by_type(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = item("K1")
    fakes.attachments.get_annotations.return_value = [
        _annotation("A1", "highlight", text="marked \x1b[0m" + "w" * 5000, comment="why", page="3"),
        _annotation("A2", "note", comment="loose"),
        _annotation("A3", "underline", text="u"),
    ]  # fmt: skip

    everything = fakes.tools().get_annotations("K1")
    only = fakes.tools().get_annotations("K1", types=["highlight", "underline"])

    assert everything["count"] == 3
    first = everything["annotations"][0]
    assert "\x1b" not in first["text"]
    assert len(first["text"]) <= agent_tools.ANNOTATION_CAP
    assert (first["comment"], first["page"]) == ("why", "3")
    assert [a["key"] for a in only["annotations"]] == ["A1", "A3"]


def test_an_unknown_annotation_type_is_a_usage_error(fakes: Fakes) -> None:
    tools = fakes.tools()
    with pytest.raises(UsageError, match="Unknown annotation type"):
        tools.get_annotations("K1", types=["doodle"])


def test_annotations_of_an_unknown_item_are_not_found(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = None
    tools = fakes.tools()
    with pytest.raises(NotFound):
        tools.get_annotations("NOPE")


# ---- get_item_text --------------------------------------------------------------------------


def test_pdf_text_is_truncated_and_says_so(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = item("K1")
    fakes.text.get_fulltext.return_value = "a" * 50 + "\x1b[31m" + "b" * 50

    result = fakes.tools().get_item_text("K1", max_chars=60)

    assert result["available"] is True
    # 50 + the 4 characters left of the escape sequence + 50
    assert (result["truncated"], result["total_chars"], len(result["text"])) == (True, 104, 60)
    assert "\x1b" not in result["text"]


def test_short_pdf_text_is_returned_whole(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = item("K1")
    fakes.text.get_fulltext.return_value = "hello"
    result = fakes.tools().get_item_text("K1")
    assert (result["text"], result["truncated"], result["total_chars"]) == ("hello", False, 5)


def test_max_chars_is_clamped_to_the_hard_limit(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = item("K1")
    fakes.text.get_fulltext.return_value = "x" * (agent_tools.MAX_TEXT_CHARS + 500)

    result = fakes.tools().get_item_text("K1", max_chars=10**9)

    assert len(result["text"]) == agent_tools.MAX_TEXT_CHARS
    assert result["truncated"] is True


def test_an_item_without_readable_pdf_text_is_not_available(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = item("K1")
    fakes.text.get_fulltext.return_value = None
    assert fakes.tools().get_item_text("K1") == {
        "key": "K1", "available": False, "text": "", "truncated": False,
    }  # fmt: skip


def test_pdf_text_of_an_unknown_item_is_not_found(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = None
    tools = fakes.tools()
    with pytest.raises(NotFound):
        tools.get_item_text("NOPE")
    fakes.text.get_fulltext.assert_not_called()


# ---- get_bibliography -----------------------------------------------------------------------


def test_bibliography_formats_the_found_items_and_lists_the_missing(fakes: Fakes) -> None:
    fakes.items.get_item.side_effect = lambda key: item(key) if key != "GONE" else None

    result = fakes.tools().get_bibliography(["A", "GONE", "B"], style="ieee", render="markdown")

    assert result["missing"] == ["GONE"]
    assert (result["count"], result["style"], result["render"]) == (2, "ieee", "markdown")
    assert result["bibliography"] == "A; B"
    assert fakes.formatted[0][1:] == ("ieee", "markdown")


def test_bibliography_of_only_missing_keys_does_not_call_the_formatter(fakes: Fakes) -> None:
    fakes.items.get_item.return_value = None
    result = fakes.tools().get_bibliography(["X"])
    assert (result["count"], result["bibliography"], result["missing"]) == (0, "", ["X"])
    assert fakes.formatted == []


def test_bibliography_key_limits(fakes: Fakes) -> None:
    tools = fakes.tools()
    with pytest.raises(UsageError, match="at least one"):
        tools.get_bibliography([])
    with pytest.raises(UsageError, match="At most 100"):
        tools.get_bibliography([f"K{i}" for i in range(101)])


# ---- describe_cli ---------------------------------------------------------------------------


def test_describe_cli_delegates(fakes: Fakes) -> None:
    assert fakes.tools().describe_cli(["item", "list"]) == {"described": ["item", "list"]}
    assert fakes.tools().describe_cli() == {"described": None}


# ---- the tools stay read-only ---------------------------------------------------------------


def _public_tools() -> List[str]:
    return [
        name
        for name, member in inspect.getmembers(AgentTools, inspect.isfunction)
        if not name.startswith("_")
    ]


def test_every_public_tool_is_declared_and_every_declared_tool_exists() -> None:
    assert sorted(_public_tools()) == sorted(agent_tools.TOOL_COMMANDS)


def test_every_tool_corresponds_to_a_read_only_command_or_to_none() -> None:
    """A write capability can't join the MCP surface without changing COMMAND_EFFECTS on
    purpose: each tool names the CLI command it mirrors, and that command must only read."""
    for tool, command in agent_tools.TOOL_COMMANDS.items():
        if command is not None:
            assert COMMAND_EFFECTS[command] == "read", f"{tool} mirrors {command}"
