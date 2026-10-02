import argparse
import json
from typing import Any, List, Optional
from unittest.mock import create_autospec, patch

import pytest

from zotero_cli.cli.commands.search_cmd import SearchCommand
from zotero_cli.cli.main import build_parser
from zotero_cli.core.exceptions import NotFound, UsageError, ZoteroCliError
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        yield mock_get.return_value


@pytest.fixture
def search_cmd():
    return SearchCommand()


def test_search_by_doi(search_cmd, mock_gateway):
    args = argparse.Namespace(query=None, doi="10.1234/5678", title=None, limit=50, user=False)

    item = ZoteroItem.from_raw_zotero_item(
        {
            "key": "KEY1",
            "data": {"title": "Test Paper", "DOI": "10.1234/5678", "creators": [], "date": "2023"},
        }
    )
    mock_gateway.get_items_by_doi.return_value = [item]

    search_cmd.execute(args)

    mock_gateway.get_items_by_doi.assert_called_once_with("10.1234/5678")


def test_search_by_title(search_cmd, mock_gateway):
    args = argparse.Namespace(query=None, doi=None, title="Transformer", limit=50, user=False)

    item = ZoteroItem.from_raw_zotero_item(
        {
            "key": "KEY1",
            "data": {"title": "Attention is all you need", "creators": [], "date": "2017"},
        }
    )
    mock_gateway.search_items.return_value = [item]

    search_cmd.execute(args)

    mock_gateway.search_items.assert_called_once()
    query = mock_gateway.search_items.call_args[0][0]
    assert query.q == "Transformer"
    assert query.qmode == "titleCreatorYear"


def test_search_by_query(search_cmd, mock_gateway):
    args = argparse.Namespace(query="Deep Learning", doi=None, title=None, limit=50, user=False)

    item = ZoteroItem.from_raw_zotero_item(
        {"key": "KEY1", "data": {"title": "Deep Learning Book", "creators": [], "date": "2016"}}
    )
    mock_gateway.search_items.return_value = [item]

    search_cmd.execute(args)

    mock_gateway.search_items.assert_called_once()
    query = mock_gateway.search_items.call_args[0][0]
    assert query.q == "Deep Learning"


def test_search_no_args(search_cmd, mock_gateway):
    args = argparse.Namespace(query=None, doi=None, title=None, limit=50, user=False)
    with pytest.raises(ZoteroCliError):
        search_cmd.execute(args)
    mock_gateway.get_items_by_doi.assert_not_called()
    mock_gateway.search_items.assert_not_called()


def test_search_no_results(search_cmd, mock_gateway):
    args = argparse.Namespace(query="Nothing", doi=None, title=None, limit=50, user=False)
    mock_gateway.search_items.return_value = []
    search_cmd.execute(args)
    mock_gateway.search_items.assert_called_once()


def test_search_by_query_with_bracketed_text_renders_literally(search_cmd, mock_gateway, capsys):
    """Issue #253: a query containing a bracketed substring must not be
    silently consumed/reinterpreted as Rich markup (e.g. treated as a
    style toggle) - it must render as literal text."""
    args = argparse.Namespace(
        query="[Retracted] Studies", doi=None, title=None, limit=50, user=False
    )
    mock_gateway.search_items.return_value = []

    search_cmd.execute(args)

    out = capsys.readouterr().out
    assert "[Retracted] Studies" in out


def test_search_stops_reading_at_the_limit(search_cmd, mock_gateway):
    """Issue #438: every page of hits was fetched before --limit applied."""
    pulled = []

    def hits():
        for n in range(1000):
            pulled.append(n)
            yield ZoteroItem.from_raw_zotero_item(
                {"key": f"K{n:07d}", "data": {"title": "t", "creators": [], "date": "2020"}}
            )

    mock_gateway.search_items.return_value = hits()
    search_cmd.execute(argparse.Namespace(query="aa", doi=None, title=None, limit=5, user=False))

    assert len(pulled) == 5


# ---- Issue #562: filters, paging and sorting -------------------------------------------------


def _paper(
    key: str, date: Optional[str] = None, added: Optional[str] = None, title: str = "T"
) -> ZoteroItem:
    return ZoteroItem(
        key=key,
        version=1,
        item_type="journalArticle",
        title=title,
        date=date,
        date_added=added,
        authors=["A B"],
    )


def _parse(*argv: str) -> argparse.Namespace:
    return build_parser().parse_args(["search", *argv])


def _run(gateway: Any, *argv: str, collection_key: Optional[str] = "COL1") -> Any:
    service = create_autospec(CollectionService, instance=True)
    service.resolve_collection.return_value = collection_key
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_collection_service", return_value=service
    ):
        SearchCommand().execute(_parse(*argv))
    return service


def _keys_printed(capsys: pytest.CaptureFixture[str]) -> List[str]:
    return [row["key"] for row in json.loads(capsys.readouterr().out)]


def test_the_new_options_parse_with_their_defaults_when_absent() -> None:
    args = _parse("deep learning")
    assert (args.start, args.tag, args.item_type, args.collection) == (0, None, None, None)
    assert (args.year, args.added_since, args.added_until) == (None, None, None)
    assert (args.sort, args.direction) == (None, None)


def test_every_new_option_parses() -> None:
    args = _parse(
        "--tag", "a", "--tag", "b", "--type", "book", "--collection", "Inbox", "--year", "2018-2022",
        "--added-since", "2026-01-01", "--added-until", "2026-02-01", "--sort", "title",
        "--direction", "asc", "--start", "5",
    )  # fmt: skip
    assert args.tag == ["a", "b"]
    assert (args.item_type, args.collection, args.year) == ("book", "Inbox", "2018-2022")
    assert (args.sort, args.direction, args.start) == ("title", "asc", 5)


def test_a_tag_can_be_excluded_with_the_equals_form() -> None:
    assert _parse("--tag=-archived", "x").tag == ["-archived"]


def test_filters_alone_are_a_search(mock_gateway: Any, capsys: pytest.CaptureFixture[str]) -> None:
    mock_gateway.search_items.return_value = [_paper("K1")]

    _run(mock_gateway, "--tag", "to-read", "--tag", "ml", "--type", "book", "--format", "json")

    query = mock_gateway.search_items.call_args[0][0]
    assert query.q is None
    assert (query.tag, query.item_type, query.collection) == (["to-read", "ml"], "book", None)
    assert _keys_printed(capsys) == ["K1"]


def test_filters_combine_with_a_keyword(mock_gateway: Any) -> None:
    mock_gateway.search_items.return_value = []

    _run(mock_gateway, "attention", "--tag", "ml")

    query = mock_gateway.search_items.call_args[0][0]
    assert (query.q, query.qmode, query.tag) == ("attention", "titleCreatorYear", ["ml"])


def test_a_collection_is_resolved_to_its_key(mock_gateway: Any) -> None:
    mock_gateway.search_items.return_value = []

    service = _run(mock_gateway, "--collection", "Included", collection_key="KEY123")

    service.resolve_collection.assert_called_once_with("Included")
    assert mock_gateway.search_items.call_args[0][0].collection == "KEY123"


def test_an_unknown_collection_is_an_error(mock_gateway: Any) -> None:
    with pytest.raises(NotFound, match="Collection 'Nope' not found"):
        _run(mock_gateway, "--collection", "Nope", collection_key=None)
    mock_gateway.search_items.assert_not_called()


def test_sort_and_direction_reach_the_query(mock_gateway: Any) -> None:
    mock_gateway.search_items.return_value = []

    _run(mock_gateway, "x", "--sort", "dateAdded", "--direction", "asc")

    query = mock_gateway.search_items.call_args[0][0]
    assert (query.sort, query.direction) == ("dateAdded", "asc")


def test_without_sort_options_the_default_order_is_kept(mock_gateway: Any) -> None:
    mock_gateway.search_items.return_value = []

    _run(mock_gateway, "x")

    query = mock_gateway.search_items.call_args[0][0]
    assert (query.sort, query.direction) == ("date", "desc")


def test_a_year_range_is_applied_to_the_results(
    mock_gateway: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_gateway.search_items.return_value = [
        _paper("OLD", "2010"),
        _paper("IN1", "2019-05-01"),
        _paper("IN2", "May 2021"),
        _paper("NEW", "2024"),
        _paper("NODATE"),
    ]

    _run(mock_gateway, "x", "--year", "2018-2022", "--format", "json")

    assert _keys_printed(capsys) == ["IN1", "IN2"]


def test_date_added_bounds_are_applied_to_the_results(
    mock_gateway: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_gateway.search_items.return_value = [
        _paper("A", added="2026-01-10T00:00:00Z"),
        _paper("B", added="2026-02-10T00:00:00Z"),
        _paper("C", added="2026-03-10T00:00:00Z"),
    ]

    _run(
        mock_gateway,
        "x",
        "--added-since",
        "2026-02-01",
        "--added-until",
        "2026-02-28",
        "--format",
        "json",
    )

    assert _keys_printed(capsys) == ["B"]


def test_start_and_limit_page_through_the_results(
    mock_gateway: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_gateway.search_items.return_value = iter([_paper(f"K{i}") for i in range(6)])

    _run(mock_gateway, "x", "--start", "2", "--limit", "3", "--format", "json")

    assert _keys_printed(capsys) == ["K2", "K3", "K4"]


def test_paging_counts_only_results_that_pass_the_filters(
    mock_gateway: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_gateway.search_items.return_value = iter(
        [_paper("A", "2020"), _paper("B", "1999"), _paper("C", "2021"), _paper("D", "2022")]
    )

    _run(mock_gateway, "x", "--year", "2020-", "--start", "1", "--limit", "1", "--format", "json")

    assert _keys_printed(capsys) == ["C"]


def test_a_doi_cannot_be_combined_with_filters(mock_gateway: Any) -> None:
    with pytest.raises(UsageError, match="--doi names one item"):
        _run(mock_gateway, "--doi", "10.1/x", "--tag", "ml")


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["x", "--year", "20"], "--year"),
        (["x", "--year", "2022-2018"], "ends before it starts"),
        (["x", "--added-since", "last week"], "--added-since"),
        (["x", "--added-until", "2026-02-30"], "--added-until"),
        (["x", "--start", "-1"], "--start can't be negative"),
    ],
)
def test_bad_values_are_usage_errors_before_any_request(
    mock_gateway: Any, argv: List[str], message: str
) -> None:
    with pytest.raises(UsageError, match=message):
        _run(mock_gateway, *argv)
    mock_gateway.search_items.assert_not_called()


def test_nothing_to_search_for_says_what_would_do(mock_gateway: Any) -> None:
    with pytest.raises(UsageError, match="--tag"):
        _run(mock_gateway)
