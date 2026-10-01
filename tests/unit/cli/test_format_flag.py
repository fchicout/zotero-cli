"""Issue #380: `--format` means output rendering, and the list-style commands
all offer table/json/csv with nothing but the data on stdout."""

import argparse
import csv
import io
import json
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.main import build_parser
from zotero_cli.cli.presenters import records
from zotero_cli.core.zotero_item import ZoteroItem

COLS = [records.Column("key", "Key"), records.Column("title", "Title")]


def _stdout(capsys):
    out, err = capsys.readouterr()
    return out, err


# ---- the shared presenter ---------------------------------------------------


def test_json_is_a_list_of_objects_in_column_order():
    out = io.StringIO()
    records.render_data([{"key": "K1", "title": "A", "extra": 1}], COLS, "json", out)
    assert json.loads(out.getvalue()) == [{"key": "K1", "title": "A"}]


def test_csv_has_a_header_flattens_lists_and_guards_formulas():
    out = io.StringIO()
    rows = [{"key": "K1", "title": ['=HYPERLINK("http://evil")', "b"]}]
    records.render_data(rows, COLS, "csv", out)
    parsed = list(csv.reader(io.StringIO(out.getvalue())))
    assert parsed[0] == ["key", "title"]
    assert parsed[1][1].startswith("'")


def test_csv_and_markdown_strip_terminal_controls():
    for fmt in ("csv", "markdown"):
        out = io.StringIO()
        records.render_data([{"key": "K\x1b[31m1", "title": "t"}], COLS, fmt, out)
        assert "\x1b" not in out.getvalue()


def test_empty_results_are_still_valid_documents():
    out = io.StringIO()
    records.render_data([], COLS, "json", out)
    assert json.loads(out.getvalue()) == []
    out = io.StringIO()
    records.render_data([], COLS, "csv", out)
    assert out.getvalue().strip() == "key,title"


# ---- every command accepts it ------------------------------------------------

PARSES = [
    ["search", "x", "--format", "json"],
    ["collection", "list", "--format", "csv"],
    ["tag", "list", "--format", "json"],
    ["report", "stats", "--format", "csv"],
    ["slr", "list", "pending", "--format", "json"],
    ["slr", "list", "included", "--format", "csv"],
    ["slr", "list", "excluded", "--format", "json"],
    ["slr", "list", "qa-approved", "--format", "csv"],
    ["system", "jobs", "list", "--format", "json"],
]


@pytest.mark.parametrize("argv", PARSES)
def test_format_is_accepted(argv):
    assert build_parser().parse_args(argv).format in ("json", "csv")


@pytest.mark.parametrize("argv", [p[:-2] for p in PARSES])
def test_format_defaults_to_the_old_human_output(argv):
    assert build_parser().parse_args(argv).format in ("table", "tree")


def test_unknown_format_is_refused():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["search", "x", "--format", "xml"])


# ---- search ------------------------------------------------------------------


def _item(key="K1", title="Attention", doi="10.1/x"):
    return ZoteroItem.from_raw_zotero_item(
        {
            "key": key,
            "data": {
                "title": title,
                "DOI": doi,
                "date": "2017-06-12",
                "creators": [{"creatorType": "author", "firstName": "A", "lastName": "Vaswani"}],
            },
        }
    )


def _search(fmt, hits):
    from zotero_cli.cli.commands.search_cmd import SearchCommand

    args = argparse.Namespace(
        query="attention", doi=None, title=None, limit=50, user=False, format=fmt
    )
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as get:
        get.return_value.search_items.return_value = hits
        SearchCommand().execute(args)


def test_search_json_keeps_stdout_clean(capsys):
    _search("json", [_item()])
    out, err = _stdout(capsys)
    data = json.loads(out)
    assert data[0]["key"] == "K1"
    assert data[0]["year"] == "2017"
    assert data[0]["authors"] == ["A Vaswani"]
    assert "Searching for" in err


def test_search_json_with_no_hits_is_an_empty_list(capsys):
    _search("json", [])
    out, err = _stdout(capsys)
    assert json.loads(out) == []
    assert "No items found" not in out


def test_search_json_does_not_truncate_long_titles(capsys):
    _search("json", [_item(title="T" * 200)])
    assert len(json.loads(capsys.readouterr().out)[0]["title"]) == 200


def test_search_table_is_unchanged(capsys):
    _search("table", [_item()])
    out, _ = _stdout(capsys)
    assert "Search Results" in out


# ---- collection list ---------------------------------------------------------

COLLECTIONS = [
    {"key": "C1", "data": {"name": "Root"}, "meta": {"numItems": 3}},
    {"key": "C2", "data": {"name": "Child", "parentCollection": "C1"}, "meta": {"numItems": 0}},
]


def _collection_list(**overrides):
    from zotero_cli.cli.commands.collection_cmd import CollectionCommand

    args = argparse.Namespace(verb="list", table=False, format="tree", user=False)
    for k, v in overrides.items():
        setattr(args, k, v)
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as get:
        get.return_value.get_all_collections.return_value = COLLECTIONS
        CollectionCommand().execute(args)


def test_collection_list_json_is_flat_records(capsys):
    _collection_list(format="json")
    assert json.loads(capsys.readouterr().out) == [
        {"key": "C1", "name": "Root", "parent": "", "num_items": 3},
        {"key": "C2", "name": "Child", "parent": "C1", "num_items": 0},
    ]


def test_collection_list_csv(capsys):
    _collection_list(format="csv")
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert rows[1]["parent"] == "C1"


def test_collection_list_tree_is_still_the_default(capsys):
    _collection_list()
    assert "Zotero Library (ROOT)" in capsys.readouterr().out


def test_collection_list_table_flag_still_works(capsys):
    _collection_list(table=True)
    assert "Zotero Collections" in capsys.readouterr().out


# ---- tag list ----------------------------------------------------------------


def _tag_list(fmt):
    from zotero_cli.cli.commands.tag_cmd import TagCommand

    args = argparse.Namespace(verb="list", format=fmt, user=False)
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as get,
        patch("zotero_cli.infra.factory.GatewayFactory.get_tag_service"),
    ):
        get.return_value.get_tags.return_value = ["beta", "alpha"]
        TagCommand().execute(args)


def test_tag_list_json_is_sorted_objects(capsys):
    _tag_list("json")
    assert json.loads(capsys.readouterr().out) == [{"tag": "alpha"}, {"tag": "beta"}]


def test_tag_list_csv(capsys):
    _tag_list("csv")
    assert capsys.readouterr().out.split() == ["tag", "alpha", "beta"]


def test_tag_list_default_is_still_one_tag_per_line(capsys):
    _tag_list("table")
    assert capsys.readouterr().out.split() == ["alpha", "beta"]


# ---- report stats ------------------------------------------------------------


def _stats(fmt):
    from zotero_cli.cli.commands.report_cmd import ReportCommand

    def item(kind, year):
        i = MagicMock()
        i.item_type = kind
        i.raw_data = {"data": {"date": year, "creators": [{"name": "A"}]}}
        return i

    gateway = MagicMock()
    gateway.get_all_items.return_value = [
        item("journalArticle", "2023"),
        item("book", "2023"),
        item("journalArticle", "2021"),
    ]
    args = argparse.Namespace(report_type="stats", collection=None, format=fmt, user=False)
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway):
        ReportCommand().execute(args)


def test_report_stats_json_is_one_object(capsys):
    _stats("json")
    data = json.loads(capsys.readouterr().out)
    assert data["scope"] == "Full Library"
    assert data["total_items"] == 3
    assert data["total_creators"] == 3
    assert data["by_type"][0] == {"type": "journalArticle", "count": 2, "percent": 66.67}
    assert data["by_year"] == [{"year": "2021", "count": 1}, {"year": "2023", "count": 2}]


def test_report_stats_csv_is_long_form(capsys):
    _stats("csv")
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert {r["section"] for r in rows} == {"summary", "type", "year"}
    assert next(r for r in rows if r["label"] == "total_items")["count"] == "3"


def test_report_stats_table_is_unchanged(capsys):
    _stats("table")
    assert "Library Global Metrics" in capsys.readouterr().out


# ---- slr list ----------------------------------------------------------------


def _decided(key, phase="title_abstract", title="A paper"):
    item = MagicMock()
    item.item_key = key
    item.phase = phase
    item.source_collection = "raw_acm"
    item.reason = "IC1"
    item.title = title
    return item


def _slr_list(verb, fmt, items):
    from zotero_cli.cli.commands.slr.list_cmd import ListCommand

    args = argparse.Namespace(
        list_verb=verb,
        tree="raw_acm",
        format=fmt,
        user=False,
        ta=False,
        fullscreen=False,
        qa=None,
        csv=None,
        json=None,
        xlsx=None,
        ods=None,
    )
    with patch("zotero_cli.infra.factory.GatewayFactory.get_slr_status_service") as get:
        service = get.return_value
        service.get_pending_items.return_value = items
        service.get_decided_items.return_value = items
        ListCommand.execute(args)


@pytest.mark.parametrize("verb", ["pending", "included", "excluded", "qa-approved"])
def test_slr_list_json(verb, capsys):
    _slr_list(verb, "json", [_decided("K2", title="B" * 120), _decided("K1")])
    data = json.loads(capsys.readouterr().out)
    assert [d["key"] for d in data] == ["K1", "K2"]
    assert len(data[1]["title"]) == 120
    assert set(data[0]) == {"key", "phase", "source", "reason", "title"}


@pytest.mark.parametrize("verb", ["pending", "included"])
def test_slr_list_json_with_nothing_found_is_an_empty_list(verb, capsys):
    _slr_list(verb, "json", [])
    assert json.loads(capsys.readouterr().out) == []


def test_slr_list_table_is_unchanged(capsys):
    _slr_list("pending", "table", [_decided("K1")])
    assert "Pending SLR Items" in capsys.readouterr().out


# ---- system jobs list --------------------------------------------------------


def test_jobs_list_json(capsys):
    from zotero_cli.cli.commands.system_cmd import SystemCommand

    job = MagicMock(id=7, task_type="fetch_pdf", item_key="K1", status="FAILED", attempts=2)
    job.next_retry_at = None
    job.last_error = "boom"
    args = argparse.Namespace(
        verb="jobs", jobs_verb="list", type=None, limit=50, format="json", user=False
    )
    with patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as get:
        get.return_value.list_jobs.return_value = [job]
        SystemCommand().execute(args)
    assert json.loads(capsys.readouterr().out) == [
        {
            "id": 7,
            "type": "fetch_pdf",
            "item_key": "K1",
            "status": "FAILED",
            "attempts": 2,
            "next_retry": "",
            "error": "boom",
        }
    ]


# ---- --as for export types, --format as the deprecated alias ------------------

EXPORTS = [
    (["item", "export", "--key", "K", "--output", "o"], "bibtex"),
    (["collection", "export", "--collection", "C", "--output", "o"], "bibtex"),
]


@pytest.mark.parametrize("argv, default", EXPORTS)
def test_export_type_defaults_and_as_is_silent(argv, default, capsys):
    assert build_parser().parse_args(argv).export_format == default
    assert build_parser().parse_args([*argv, "--as", "ris"]).export_format == "ris"
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("argv, default", EXPORTS)
def test_old_format_spelling_on_exports_warns_and_still_works(argv, default, capsys):
    args = build_parser().parse_args([*argv, "--format", "md"])
    assert args.export_format == "md"
    assert "`--format` is deprecated; use `--as`" in capsys.readouterr().err


def test_item_inspect_as_and_deprecated_format(capsys):
    assert build_parser().parse_args(["item", "inspect", "K", "--as", "ris"]).export_format == "ris"
    assert capsys.readouterr().err == ""
    assert (
        build_parser().parse_args(["item", "inspect", "K", "--format", "bibtex"]).export_format
        == "bibtex"
    )
    assert "deprecated; use `--as`" in capsys.readouterr().err


def test_export_type_rejects_output_renderings():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["item", "export", "--key", "K", "--output", "o", "--as", "json"])


def test_as_and_format_together_are_refused():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["item", "export", "--key", "K", "--output", "o", "--as", "ris", "--format", "ris"]
        )
