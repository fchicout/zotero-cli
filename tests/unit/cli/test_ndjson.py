"""`--format ndjson`: one JSON object per line, written as results arrive (Issue #556)."""

import argparse
import io
import json
from typing import Any, Iterator, List
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.search_cmd import SearchCommand
from zotero_cli.cli.main import build_parser
from zotero_cli.cli.presenters import records
from zotero_cli.core.zotero_item import ZoteroItem

COLUMNS = [records.Column("key", "Key"), records.Column("title", "Title")]


def test_one_object_per_line_with_the_same_keys_as_json() -> None:
    out = io.StringIO()
    rows = [{"key": "K1", "title": "A"}, {"key": "K2", "title": "B", "extra": "ignored"}]

    records.render_ndjson(rows, COLUMNS, out)

    lines = out.getvalue().splitlines()
    assert [json.loads(line) for line in lines] == [
        {"key": "K1", "title": "A"},
        {"key": "K2", "title": "B"},
    ]
    assert out.getvalue().endswith("\n")


def test_no_records_means_no_output() -> None:
    out = io.StringIO()
    records.render_ndjson([], COLUMNS, out)
    assert out.getvalue() == ""


def test_unicode_is_kept_and_control_characters_are_escaped() -> None:
    out = io.StringIO()
    records.render_ndjson([{"key": "K", "title": "Naïve \x1b[31m red"}], COLUMNS, out)

    line = out.getvalue()
    assert "Naïve" in line
    assert "\x1b" not in line  # escaped as \u001b by JSON, never raw on the terminal
    assert json.loads(line)["title"] == "Naïve \x1b[31m red"
    assert out.getvalue().count("\n") == 1


def test_a_missing_value_is_an_empty_string_like_json() -> None:
    out = io.StringIO()
    records.render_ndjson([{"key": "K"}], COLUMNS, out)
    assert json.loads(out.getvalue()) == {"key": "K", "title": ""}


def test_records_are_written_as_they_are_produced() -> None:
    """The first line is out (and flushed) before the second record exists."""
    events: List[str] = []

    class Out(io.StringIO):
        def write(self, text: str) -> int:
            events.append("write")
            return super().write(text)

        def flush(self) -> None:
            events.append("flush")
            super().flush()

    def produce() -> Iterator[dict]:
        events.append("make 1")
        yield {"key": "K1", "title": "A"}
        events.append("make 2")
        yield {"key": "K2", "title": "B"}

    records.render_ndjson(produce(), COLUMNS, Out())

    assert events == ["make 1", "write", "flush", "make 2", "write", "flush"]


def test_render_data_dispatches_ndjson_and_accepts_a_generator() -> None:
    out = io.StringIO()
    records.render_data((r for r in [{"key": "K1", "title": "A"}]), COLUMNS, "ndjson", out)
    assert json.loads(out.getvalue()) == {"key": "K1", "title": "A"}


def test_render_data_still_takes_a_generator_for_json() -> None:
    out = io.StringIO()
    records.render_data((r for r in [{"key": "K1", "title": "A"}]), COLUMNS, "json", out)
    assert json.loads(out.getvalue()) == [{"key": "K1", "title": "A"}]


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
def test_the_list_style_commands_accept_ndjson(argv: List[str]) -> None:
    assert build_parser().parse_args([*argv, "--format", "ndjson"]).format == "ndjson"


def test_a_command_whose_json_is_one_object_does_not_offer_ndjson() -> None:
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["report", "stats", "--format", "ndjson"])
    assert exit_info.value.code == 2


def _paper(key: str) -> ZoteroItem:
    return ZoteroItem(key=key, version=1, item_type="book", title=f"T {key}", authors=["A B"])


def test_search_streams_ndjson_a_result_at_a_time(capsys: pytest.CaptureFixture[str]) -> None:
    seen_when_second_was_fetched: List[str] = []

    def hits() -> Iterator[ZoteroItem]:
        yield _paper("K1")
        # by the time the generator is asked for the second result, K1 is already printed
        seen_when_second_was_fetched.append(capsys.readouterr().out)
        yield _paper("K2")

    gateway: Any
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as get:
        gateway = get.return_value
        gateway.search_items.return_value = hits()
        args = build_parser().parse_args(["search", "x", "--format", "ndjson"])
        SearchCommand().execute(argparse.Namespace(**vars(args)))

    assert [json.loads(line)["key"] for line in seen_when_second_was_fetched[0].splitlines()] == [
        "K1"
    ]
    assert [json.loads(line)["key"] for line in capsys.readouterr().out.splitlines()] == ["K2"]


def test_search_ndjson_honours_filters_start_and_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as get:
        get.return_value.search_items.return_value = iter([_paper(f"K{i}") for i in range(6)])
        args = build_parser().parse_args(
            ["search", "x", "--format", "ndjson", "--start", "2", "--limit", "2"]
        )
        SearchCommand().execute(args)

    keys = [json.loads(line)["key"] for line in capsys.readouterr().out.splitlines()]
    assert keys == ["K2", "K3"]
