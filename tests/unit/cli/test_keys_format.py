"""`--format keys`: one identifier per line, for xargs and `while read` (Issue #559)."""

import argparse
import io
from typing import Any, Iterator, List
from unittest.mock import create_autospec, patch

import pytest

from zotero_cli.cli.commands.collection_cmd import CollectionCommand
from zotero_cli.cli.commands.search_cmd import SearchCommand
from zotero_cli.cli.commands.tag_cmd import TagCommand
from zotero_cli.cli.main import build_parser
from zotero_cli.cli.presenters import records
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem


def _keys(rows: Any, columns: List[records.Column]) -> str:
    out = io.StringIO()
    records.render_keys(rows, columns, out)
    return out.getvalue()


ITEM_COLUMNS = [records.Column("key", "Key"), records.Column("title", "Title")]


def test_the_key_column_is_written_one_per_line() -> None:
    rows = [{"key": "K1", "title": "A"}, {"key": "K2", "title": "B"}]
    assert _keys(rows, ITEM_COLUMNS) == "K1\nK2\n"


def test_the_key_column_wins_wherever_it_is() -> None:
    columns = [records.Column("title", "Title"), records.Column("key", "Key")]
    assert _keys([{"key": "K1", "title": "A"}], columns) == "K1\n"


def test_without_a_key_column_the_first_column_is_used() -> None:
    assert _keys([{"tag": "ml"}, {"tag": "to-read"}], [records.Column("tag", "Tag")]) == (
        "ml\nto-read\n"
    )


def test_empty_values_are_skipped_and_no_records_print_nothing() -> None:
    assert _keys([{"key": ""}, {"key": "K2"}, {}], ITEM_COLUMNS) == "K2\n"
    assert _keys([], ITEM_COLUMNS) == ""
    assert _keys([{"key": "K"}], []) == ""


def test_a_value_with_line_breaks_stays_on_one_line() -> None:
    rows = [{"tag": "two\nlines\r\nand a\ttab"}]
    assert _keys(rows, [records.Column("tag", "Tag")]) == "two lines and a tab\n"


def test_control_characters_are_removed() -> None:
    assert _keys([{"tag": "red\x1b[31m"}], [records.Column("tag", "Tag")]) == "red[31m\n"


def test_a_list_value_is_joined() -> None:
    assert _keys([{"key": ["A", "B"]}], ITEM_COLUMNS) == "A; B\n"


def test_keys_are_flushed_a_line_at_a_time() -> None:
    events: List[str] = []

    class Out(io.StringIO):
        def flush(self) -> None:
            events.append("flush")
            super().flush()

    def produce() -> Iterator[dict]:
        events.append("make 1")
        yield {"key": "K1"}
        events.append("make 2")
        yield {"key": "K2"}

    records.render_keys(produce(), ITEM_COLUMNS, Out())

    assert events == ["make 1", "flush", "make 2", "flush"]


def test_render_data_dispatches_keys() -> None:
    out = io.StringIO()
    records.render_data(iter([{"key": "K1"}]), ITEM_COLUMNS, "keys", out)
    assert out.getvalue() == "K1\n"


@pytest.mark.parametrize(
    "argv",
    [
        ["search", "x"],
        ["item", "list"],
        ["tag", "list"],
        ["collection", "list"],
        ["slr", "list", "pending"],
        ["slr", "list", "included"],
        ["slr", "list", "excluded"],
        ["system", "jobs", "list"],
    ],
)
def test_the_list_style_commands_accept_keys(argv: List[str]) -> None:
    assert build_parser().parse_args([*argv, "--format", "keys"]).format == "keys"


def test_report_stats_does_not_offer_keys() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exit_info:
        parser.parse_args(["report", "stats", "--format", "keys"])
    assert exit_info.value.code == 2


def _paper(key: str) -> ZoteroItem:
    return ZoteroItem(key=key, version=1, item_type="book", title=f"T {key}")


def test_search_prints_only_the_keys_and_streams_them(capsys: pytest.CaptureFixture[str]) -> None:
    printed_before_second: List[str] = []

    def hits() -> Iterator[ZoteroItem]:
        yield _paper("K1")
        printed_before_second.append(capsys.readouterr().out)
        yield _paper("K2")

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as get:
        get.return_value.search_items.return_value = hits()
        SearchCommand().execute(build_parser().parse_args(["search", "x", "--format", "keys"]))

    assert printed_before_second == ["K1\n"]
    captured = capsys.readouterr()
    assert captured.out == "K2\n"  # progress went to stderr, nothing else on stdout


def test_collection_list_prints_collection_keys(capsys: pytest.CaptureFixture[str]) -> None:
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_all_collections.return_value = [
        {"key": "C1", "data": {"name": "One"}},
        {"key": "C2", "data": {"name": "Two", "parentCollection": "C1"}},
    ]
    args = argparse.Namespace(verb="list", table=False, format="keys", user=False)

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway):
        CollectionCommand().execute(args)

    assert capsys.readouterr().out == "C1\nC2\n"


def test_tag_list_prints_the_tags_sorted(capsys: pytest.CaptureFixture[str]) -> None:
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_tags.return_value = ["zeta", "alpha", "mid"]
    args = argparse.Namespace(verb="list", format="keys", user=False)

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway),
        patch("zotero_cli.infra.factory.GatewayFactory.get_tag_service"),
    ):
        TagCommand().execute(args)

    assert capsys.readouterr().out == "alpha\nmid\nzeta\n"


def test_item_list_prints_item_keys() -> None:
    from zotero_cli.cli.presenters import item_list_presenter
    from zotero_cli.core.utils.terminal_safety import SafeConsole

    out = io.StringIO()
    item_list_presenter.render(
        [_paper("K1"), _paper("K2")], ["key", "title"], "keys", "Items", SafeConsole(), out
    )
    assert out.getvalue() == "K1\nK2\n"
