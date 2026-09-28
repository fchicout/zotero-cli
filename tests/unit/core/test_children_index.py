"""children_by_parent picks the cheapest way to get many parents' children
(Issues #425, #441)."""

from unittest.mock import MagicMock, Mock, patch

from tests.unit.infra.test_sqlite_children import db  # noqa: F401  (fixture)
from zotero_cli.core.models import ZoteroQuery
from zotero_cli.core.services.children_index import children_by_parent, should_scan
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway
from zotero_cli.infra.zotero_api import ZoteroAPIClient


def _note(key, parent):
    return ZoteroItem.from_raw_zotero_item(
        {"key": key, "version": 1, "data": {"itemType": "note", "parentItem": parent, "note": "x"}}
    )


class _Online(MagicMock):
    total = 0

    def count_search_results(self, query):
        return type(self).total


def test_scan_when_it_is_fewer_requests():
    gateway = _Online()
    _Online.total = 250  # 3 pages
    gateway.search_items.return_value = [_note("N1", "P1"), _note("N2", "P9"), _note("N3", "P2")]

    result = children_by_parent(gateway, ["P1", "P2", "P3", "P4"], "note")

    assert [c["key"] for c in result["P1"]] == ["N1"]
    assert [c["key"] for c in result["P2"]] == ["N3"]
    assert result["P3"] == [] and "P9" not in result
    assert gateway.search_items.call_args.args[0].item_type == "note"
    gateway.get_item_children.assert_not_called()


def test_per_parent_when_the_scan_would_be_longer():
    gateway = _Online()
    _Online.total = 20_000  # 200 pages
    gateway.get_item_children.return_value = [
        {"key": "N1", "data": {"itemType": "note"}},
        {"key": "A1", "data": {"itemType": "attachment"}},
    ]

    result = children_by_parent(gateway, ["P1", "P2", "P1"], "note")

    assert gateway.get_item_children.call_count == 2  # duplicates asked once
    assert [c["key"] for c in result["P1"]] == ["N1"]
    gateway.search_items.assert_not_called()


def test_the_threshold_is_the_page_count():
    gateway = _Online()
    _Online.total = 300
    assert not should_scan(gateway, 3, "note")
    assert should_scan(gateway, 4, "note")


def test_a_gateway_that_cannot_count_looks_up_each_parent():
    gateway = MagicMock()
    gateway.get_item_children.return_value = []
    children_by_parent(gateway, ["P1", "P2", "P3"], "note")
    assert gateway.get_item_children.call_count == 3
    gateway.search_items.assert_not_called()


def test_offline_is_one_query(db):  # noqa: F811
    gateway = SqliteZoteroGateway(db)
    result = children_by_parent(gateway, ["PAPER001", "PAPER002", "NONE"], "attachment")
    assert sorted(c["key"] for c in result["PAPER001"]) == ["LINK0001", "PDF00001"]
    assert result["PAPER002"] == [] and result["NONE"] == []


def test_online_count_reads_total_results():
    client = ZoteroAPIClient("k", "1", "user")
    response = Mock(status_code=200, headers={"Total-Results": "1234"})
    with patch.object(client.http, "get", return_value=response) as get:
        assert client.count_search_results(ZoteroQuery(item_type="note")) == 1234
    params = get.call_args.kwargs["params"]
    assert params["limit"] == 1 and params["itemType"] == "note"
