"""`report stats` and `report attachments` don't hold every item while
they read the library (Issue #439)."""

import argparse
import gc
import weakref
from typing import Iterator, List
from unittest.mock import MagicMock, patch

from zotero_cli.core.zotero_item import ZoteroItem


def _counting_items(n: int, item_type: str, alive_peak: List[int]) -> Iterator[ZoteroItem]:
    refs: List["weakref.ref[ZoteroItem]"] = []

    def items() -> Iterator[ZoteroItem]:
        for k in range(n):
            if k % 50 == 49:
                gc.collect()
                alive_peak[0] = max(alive_peak[0], sum(1 for r in refs if r() is not None))
            item = ZoteroItem.from_raw_zotero_item(
                {
                    "key": f"K{k}",
                    "version": 1,
                    "data": {
                        "itemType": item_type,
                        "title": f"t{k}",
                        "date": "2020",
                        "contentType": "application/pdf",
                        "parentItem": "P",
                    },
                }
            )
            refs.append(weakref.ref(item))
            yield item

    return items()


def _run(report_type, gateway):
    from zotero_cli.cli.commands.report_cmd import ReportCommand

    args = argparse.Namespace(report_type=report_type, collection=None, output=None, user=False)
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway):
        ReportCommand().execute(args)


def test_report_stats_keeps_no_items(capsys):
    peak = [0]
    gateway = MagicMock()
    gateway.get_all_items.return_value = _counting_items(300, "journalArticle", peak)

    _run("stats", gateway)

    assert peak[0] <= 2
    assert "Total Items: 300" in " ".join(capsys.readouterr().out.split())


def test_report_attachments_keeps_only_the_attachment_data(capsys):
    peak = [0]
    gateway = MagicMock()
    gateway.get_all_items.return_value = _counting_items(300, "attachment", peak)

    _run("attachments", gateway)

    assert peak[0] <= 2
    assert "Total Attachments: 300" in " ".join(capsys.readouterr().out.split())
