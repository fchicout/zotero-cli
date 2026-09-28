"""SLR and SDB commands fetch every paper's notes together instead of one
request per paper (Issue #425)."""

import json
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.report_service import ReportService
from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.core.services.sdb.sdb_service import SDBService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.repositories import ZoteroCollectionRepository, ZoteroNoteRepository

PAPERS = 30


class _SmallLibrary(MagicMock):
    """An online gateway in a library with 150 notes: one 2-page scan beats
    30 per-paper requests."""

    def count_search_results(self, query):
        return 150


def _paper(n: int, tags=()) -> ZoteroItem:
    return ZoteroItem.from_raw_zotero_item(
        {
            "key": f"P{n:03d}",
            "version": 1,
            "data": {"itemType": "journalArticle", "title": f"Paper {n}", "tags": [{"tag": t} for t in tags]},
        }
    )


def _decision_note(n: int, decision: str) -> ZoteroItem:
    body = {"sdb_version": "1.2", "action": "screening_decision", "decision": decision,
            "phase": "title_abstract", "reason_code": ["EC1"]}
    return ZoteroItem.from_raw_zotero_item(
        {
            "key": f"N{n:03d}",
            "version": 3,
            "data": {"itemType": "note", "parentItem": f"P{n:03d}", "note": f"<div>{json.dumps(body)}</div>"},
        }
    )


@pytest.fixture
def gateway():
    gw = _SmallLibrary()
    papers = [_paper(n, ["rsl:include"] if n % 2 else []) for n in range(PAPERS)]
    gw.get_collection_id_by_name.return_value = "COL1"
    gw.get_items_in_collection.side_effect = lambda *a, **k: iter(papers)
    gw.search_items.side_effect = lambda q: iter(
        [_decision_note(n, "accepted" if n % 2 else "rejected") for n in range(0, PAPERS, 3)]
    )
    return gw


def _assert_one_scan(gateway):
    gateway.get_item_children.assert_not_called()
    assert gateway.search_items.call_count == 1
    assert gateway.search_items.call_args.args[0].item_type == "note"


def test_sdb_filter_is_one_scan(gateway):
    items = list(gateway.get_items_in_collection("COL1"))
    included = SDBService(gateway).filter_items_by_sdb(items, included=True)
    assert [item.key for item, _ in included] == ["P003", "P009", "P015", "P021", "P027"]
    _assert_one_scan(gateway)


def test_sdb_upgrade_is_one_scan(gateway):
    stats = SDBService(gateway).upgrade_sdb_entries("COL1", dry_run=True)
    assert stats["scanned"] == 10
    _assert_one_scan(gateway)


def test_prisma_report_is_one_scan(gateway):
    report = ReportService(gateway).generate_prisma_report("COL1")
    assert report is not None and report.total_items == PAPERS
    _assert_one_scan(gateway)


def test_screening_pending_batches_through_the_repository(gateway):
    """Repositories batch like the gateway they wrap."""
    service = ScreeningService(
        MagicMock(), ZoteroCollectionRepository(gateway), ZoteroNoteRepository(gateway),
        MagicMock(), MagicMock(),
    )
    pending = service.get_pending_items("COL1")
    # untagged papers (even n) without a decision note (n not a multiple of 3)
    assert [p.key for p in pending] == [f"P{n:03d}" for n in range(0, PAPERS, 2) if n % 3]
    _assert_one_scan(gateway)


def test_slr_report_status_is_one_scan(gateway):
    """The measured case: 5,021 children requests for 5,000 papers."""
    from zotero_cli.core.services.slr.status_service import SLRStatusService

    papers = list(gateway.get_items_in_collection("RAW"))
    gateway.get_all_collections.return_value = [{"key": "RAW", "data": {"name": "raw_x"}}]
    orchestrator = MagicMock()
    orchestrator.PHASE_FLOW = [{"id": "title_abstract", "folder": "screen_ta"}]
    orchestrator.get_all_papers_in_tree.return_value = papers
    orchestrator.find_slr_hierarchy.return_value = {}

    [status] = SLRStatusService(gateway, orchestrator).get_slr_status()

    stats = status.phases["title_abstract"]
    assert (stats.accepted, stats.rejected) == (5, 5)
    assert stats.pending == PAPERS - 10
    _assert_one_scan(gateway)
