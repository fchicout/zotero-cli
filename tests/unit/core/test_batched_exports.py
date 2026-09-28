"""Exports and `report attachments` don't make one request per item
(Issues #429, #431, #432)."""

import argparse
from unittest.mock import MagicMock, patch

from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.services.export_service import ExportService
from zotero_cli.core.services.sdb.sdb_service import SDBService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.repositories import ZoteroCollectionRepository, ZoteroNoteRepository


class _SmallLibrary(MagicMock):
    def count_search_results(self, query):
        return 150  # 2 pages: a scan beats per-item lookups for 3+ items


def _item(key, item_type="journalArticle", parent=None, **data):
    raw = {"key": key, "version": 1, "data": {"itemType": item_type, "title": key, **data}}
    if parent:
        raw["data"]["parentItem"] = parent
    return ZoteroItem.from_raw_zotero_item(raw)


def test_bibtex_export_reads_sdb_data_in_one_scan():
    """12,340 requests for a 12.3k-item collection."""
    gateway = _SmallLibrary()
    papers = [_item(f"P{n}") for n in range(20)]
    gateway.get_collection_id_by_name.return_value = "COL"
    gateway.get_items_in_collection.return_value = iter(papers)
    gateway.search_items.return_value = iter([])
    bibtex = MagicMock()
    bibtex.write_file.return_value = True

    service = ExportService(ZoteroCollectionRepository(gateway), bibtex, MagicMock(), SDBService(gateway))
    assert service.export_collection("COL", "out.bib") is True

    gateway.get_item_children.assert_not_called()
    assert gateway.search_items.call_count == 1
    assert len(bibtex.write_file.call_args.args[1]) == 20


def test_markdown_export_finds_every_pdf_in_one_scan_and_downloads_by_key(tmp_path):
    """Two children requests per item: one to check, one to download."""
    gateway = _SmallLibrary()
    papers = [_item(f"P{n}") for n in range(5)]
    gateway.search_items.return_value = iter(
        [_item(f"A{n}", "attachment", parent=f"P{n}", contentType="application/pdf") for n in (0, 2)]
    )
    service = AttachmentService(
        MagicMock(), MagicMock(), MagicMock(), ZoteroNoteRepository(gateway), MagicMock()
    )
    with patch.object(service, "get_fulltext", return_value="text") as fulltext:
        stats = service.bulk_export_markdown(papers, tmp_path, max_workers=1)

    assert (stats["success"], stats["skipped"]) == (2, 3)
    gateway.get_item_children.assert_not_called()
    assert gateway.search_items.call_count == 1
    assert sorted(c.args for c in fulltext.call_args_list) == [("P0", "A0"), ("P2", "A2")]


def _run_attachments_report(gateway, collection=None):
    from zotero_cli.cli.commands.report_cmd import ReportCommand

    args = argparse.Namespace(report_type="attachments", collection=collection, output=None, user=False)
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway):
        ReportCommand().execute(args)


def test_attachments_report_on_the_library_makes_no_children_requests(capsys):
    """50,517 requests at 50k items, and each child attachment counted twice."""
    gateway = MagicMock()
    gateway.get_all_items.return_value = [
        _item("P1"),
        _item("P2"),
        _item("A1", "attachment", parent="P1", contentType="application/pdf", filesize=1024),
        _item("A2", "attachment", parent="P2", contentType="text/html", filesize=1024),
    ]

    _run_attachments_report(gateway)

    gateway.get_item_children.assert_not_called()
    out = " ".join(capsys.readouterr().out.split())
    assert "Total Attachments: 2" in out
    assert "PDF Files: 1" in out and "Other Files: 1" in out
    assert "Items Missing PDF: 1" in out


def test_attachments_report_on_a_collection_batches_the_papers():
    gateway = _SmallLibrary()
    gateway.get_collection_id_by_name.return_value = "COL"
    gateway.get_items_in_collection.return_value = [_item(f"P{n}") for n in range(10)]
    gateway.search_items.return_value = iter(
        [_item("A1", "attachment", parent="P1", contentType="application/pdf")]
    )

    _run_attachments_report(gateway, collection="COL")

    gateway.get_item_children.assert_not_called()
    assert gateway.search_items.call_args.args[0].item_type == "attachment"
